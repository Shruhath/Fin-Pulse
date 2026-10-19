import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from finpulse.db.models import Document, Entity, EntityAlias, Event, Run, Sentence
from finpulse.llm.client import LlmUnavailable, Reply
from finpulse.pipeline.llm_events import llm_extract_pending
from finpulse.preprocess.sentences import split_sentences

pytestmark = pytest.mark.db

TEXT = (
    "In the matter of Raga Securities and Finance Private Limited.\n\n"
    "The noticee was a stock broker registered with SEBI and traded for many clients over several years.\n\n"
    "I hereby impose a penalty of Rs. 4,00,000/- on Raga Securities and Finance Private Limited under "
    "section 15HB of SEBI Act."
)


class ScriptedLlm:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.prompts.append(user)
        if isinstance(self.answer, Exception):
            raise self.answer
        return Reply(json.dumps(self.answer), model, 900, 60, 4.2)


def _doc(db, sha="a" * 64, title="Order in the matter of Raga Securities and Finance Private Limited"):
    doc = Document(
        source_kind="SEBI", title=title, raw_sha256=sha, clean_text=TEXT, status="parsed",
        doc_type="SEBI adjudication order", published_at=date(2024, 5, 2),
    )  # fmt: skip
    db.add(doc)
    db.flush()
    for i, s in enumerate(split_sentences(TEXT)):
        db.add(Sentence(doc_id=doc.id, idx=i, char_start=s.start, char_end=s.end, text=s.slice(TEXT)))
    raga = Entity(slug="raga", canonical_name="Raga Securities and Finance Private Limited")
    db.add(raga)
    db.flush()
    db.add(
        EntityAlias(
            entity_id=raga.id,
            alias=raga.canonical_name,
            alias_norm="raga securities and finance",
            origin="corpus",
        )
    )
    db.flush()
    return doc, raga


def _answer(db, doc):
    last = db.query(Sentence).filter_by(doc_id=doc.id).order_by(Sentence.idx.desc()).first()
    return {
        "events": [
            {
                "trigger_sentence_id": last.idx,
                "type": "SEBI Penalty",
                "entity": "Raga Securities and Finance Private Limited",
                "arguments": {"action": "penalty", "amount_inr": "Rs. 4,00,000/-"},
            }
        ]
    }


def test_events_are_stored_against_the_trigger_sentence_and_the_resolved_entity(db):
    doc, raga = _doc(db)
    llm = ScriptedLlm(_answer(db, doc))
    stats = llm_extract_pending(db, llm, "qwen2.5:7b-instruct")
    assert (stats.documents, stats.events, stats.invalid, stats.failed) == (1, 1, 0, 0)
    assert stats.prompt_tokens == 900 and stats.seconds == pytest.approx(4.2)

    ev = db.scalar(select(Event).where(Event.doc_id == doc.id))
    assert ev.extractor == "llm" and ev.entity_id == raga.id and ev.amount_inr == Decimal(400000)
    assert ev.confidence is None and ev.schema_valid
    assert doc.clean_text[ev.trigger_start : ev.trigger_end].startswith("I hereby impose")
    run = db.scalar(select(Run).where(Run.stage == "events-llm"))
    assert run.model == "qwen2.5:7b-instruct" and run.prompt_version == "events-v2" and run.status == "done"
    assert "[S" in llm.prompts[0] and "Raga Securities" in llm.prompts[0]


def test_pruning_is_recorded_and_keeps_the_rule_detected_operative_sentence(db):
    from finpulse.pipeline.events import extract_for_document as rule_events

    doc, _ = _doc(db, sha="b" * 64)
    rule_events(db, doc)
    llm_extract_pending(db, ScriptedLlm({"events": []}), "qwen")
    kept = [s for s in db.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))]
    assert kept[-1].kept_after_prune is True


def test_rerun_skips_documents_that_have_llm_events_unless_redo(db):
    doc, _ = _doc(db, sha="c" * 64)
    llm = ScriptedLlm(_answer(db, doc))
    llm_extract_pending(db, llm, "qwen")
    assert llm_extract_pending(db, llm, "qwen").documents == 0
    assert llm_extract_pending(db, llm, "qwen", redo=True).documents == 1
    assert len(list(db.scalars(select(Event).where(Event.doc_id == doc.id, Event.extractor == "llm")))) == 1


def test_a_document_with_unusable_answers_is_counted_failed_and_the_batch_goes_on(db):
    _doc(db, sha="d" * 64)
    other = Document(
        source_kind="SEBI", title="Another", raw_sha256="e" * 64, clean_text=TEXT, status="parsed",
        doc_type="SEBI adjudication order",
    )  # fmt: skip
    db.add(other)
    db.flush()
    for i, s in enumerate(split_sentences(TEXT)):
        db.add(Sentence(doc_id=other.id, idx=i, char_start=s.start, char_end=s.end, text=s.slice(TEXT)))
    db.flush()

    class Flaky:
        n = 0

        def chat(self, model, system, user, *, schema=None, num_predict=1024):
            self.n += 1
            return Reply("garbage" if self.n <= 3 else '{"events": []}', model, 10, 1, 0.1)

    stats = llm_extract_pending(db, Flaky(), "qwen")
    assert (stats.documents, stats.failed) == (1, 1)


def test_an_unavailable_model_stops_the_stage_instead_of_failing_every_document(db):
    _doc(db, sha="f" * 64)
    with pytest.raises(LlmUnavailable):
        llm_extract_pending(db, ScriptedLlm(LlmUnavailable("down")), "qwen")
    assert db.scalar(select(Run).where(Run.stage == "events-llm", Run.status == "failed")) is not None
