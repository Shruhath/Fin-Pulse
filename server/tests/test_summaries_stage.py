import json
from datetime import date

import pytest
from sqlalchemy import select

from finpulse.db.models import Claim, Document, Entity, EntityAlias, Event, Mention, Sentence, Summary
from finpulse.llm.client import Reply
from finpulse.pipeline.summaries import summarize_documents, summarize_entities
from finpulse.preprocess.sentences import split_sentences

pytestmark = pytest.mark.db

TEXT = (
    "SEBI imposed a penalty of Rs. 4,00,000 on Raga Securities and Finance Private Limited.\n\n"
    "The penalty was imposed under section 15HB of the SEBI Act for violating the broker code of conduct.\n\n"
    "Raga Securities is a registered stock broker that traded on behalf of many clients over several years."
)


class SummaryLlm:
    def __init__(self):
        self.prompts = []

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.prompts.append(user)
        first_id = int(user.split("[S")[1].split("]")[0])
        body = {"claims": [{"text": "SEBI fined Raga Rs. 4,00,000.", "sources": [first_id, 99999999]}]}
        return Reply(json.dumps(body), model, 700, 50, 5.0)


def _seed(db, day=date(2026, 5, 1), sha="a" * 64):
    doc = Document(
        source_kind="SEBI", title="Order in the matter of Raga", raw_sha256=sha, clean_text=TEXT,
        status="analysed", published_at=day,
    )  # fmt: skip
    db.add(doc)
    db.flush()
    sents = []
    for i, sp in enumerate(split_sentences(TEXT)):
        s = Sentence(doc_id=doc.id, idx=i, char_start=sp.start, char_end=sp.end, text=sp.slice(TEXT))
        db.add(s)
        sents.append(s)
    raga = db.scalar(select(Entity).where(Entity.slug == "raga"))
    if raga is None:
        raga = Entity(slug="raga", canonical_name="Raga Securities and Finance Private Limited")
        db.add(raga)
        db.flush()
        db.add(EntityAlias(entity_id=raga.id, alias="Raga", alias_norm="raga", origin="corpus"))
    db.flush()
    for s in sents:
        db.add(
            Mention(doc_id=doc.id, sentence_id=s.id, entity_id=raga.id, char_start=s.char_start,
                    char_end=s.char_start + 4, surface=TEXT[s.char_start : s.char_start + 4], ner_model="t")
        )  # fmt: skip
    db.add(Event(doc_id=doc.id, entity_id=raga.id, type="SEBI Penalty", trigger_start=sents[0].char_start,
                 trigger_end=sents[0].char_end, extractor="rules"))  # fmt: skip
    db.flush()
    return doc, raga, sents


def test_document_summary_stores_claims_with_only_valid_citations(db):
    doc, _, sents = _seed(db)
    llm = SummaryLlm()
    stats = summarize_documents(db, llm, "llama3.1:8b-instruct-q4_K_M")
    assert (stats.summaries, stats.claims, stats.failed, stats.dropped_sources) == (1, 1, 0, 1)

    summary = db.scalar(select(Summary).where(Summary.doc_id == doc.id))
    assert summary.scope == "document" and summary.prompt_version == "summary-v1"
    (claim,) = db.scalars(select(Claim).where(Claim.summary_id == summary.id))
    assert claim.verification == "unverified" and claim.nli_entail is None
    assert claim.cited == [claim.evidence_sentence_id] and claim.evidence_sentence_id in {s.id for s in sents}
    assert f"[S{sents[0].id}] SEBI imposed" in llm.prompts[0]  # the rule-detected trigger is always shown


def test_rerun_skips_unless_redo_and_replaces_the_old_summary(db):
    doc, _, _ = _seed(db, sha="b" * 64)
    llm = SummaryLlm()
    summarize_documents(db, llm, "m")
    assert summarize_documents(db, llm, "m").summaries == 0
    assert summarize_documents(db, llm, "m", redo=True).summaries == 1
    assert len(list(db.scalars(select(Summary).where(Summary.doc_id == doc.id)))) == 1


def test_entity_summary_gathers_mention_sentences_across_documents(db):
    _, raga, _ = _seed(db, day=date(2026, 5, 1), sha="c" * 64)
    _seed(db, day=date(2026, 6, 1), sha="d" * 64)
    llm = SummaryLlm()
    stats = summarize_entities(db, llm, "m", window="all", top=5)
    assert stats.summaries == 1
    summary = db.scalar(select(Summary).where(Summary.entity_id == raga.id))
    assert summary.scope == "entity_window" and summary.window_end == date(2026, 6, 1)
    assert llm.prompts[0].count("[S") >= 6  # evidence from both documents
    assert summarize_entities(db, llm, "m", window="all", top=5).summaries == 1
    assert len(list(db.scalars(select(Summary).where(Summary.entity_id == raga.id)))) == 1


def test_documents_with_too_little_evidence_are_skipped(db):
    db.add(
        Document(source_kind="SEBI", title="Tiny", raw_sha256="e" * 64, clean_text="Short.", status="parsed")
    )
    db.flush()
    assert summarize_documents(db, SummaryLlm(), "m").summaries == 0
