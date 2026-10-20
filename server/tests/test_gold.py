import json
import xml.etree.ElementTree as ET
from datetime import date

import pytest
from sqlalchemy import select

from finpulse.db.models import Agreement, Annotation, Document, Entity, Event, GoldPassage, Mention, Sentence
from finpulse.eval.agreement import GATES, cohen_kappa, compute_agreement, fleiss_kappa, span_f1
from finpulse.eval.gold import evaluate_events, evaluate_ner, load_gold, sentiment_examples
from finpulse.eval.rouge import rouge, rouge_l, rouge_n
from finpulse.eval.summaries import evaluate_summaries, import_references
from finpulse.gold.labelstudio import import_export, label_config, tasks
from finpulse.gold.select import select_passages
from finpulse.llm.client import Reply
from finpulse.pipeline.events import extract_for_document
from finpulse.preprocess.sentences import split_sentences
from tests.fakes import FakeJudge

pytestmark = pytest.mark.db

FILLER = " ".join(
    f"The broker held trading member number {i} with the exchange and filed its returns on every due date."
    for i in range(20)
)
CORE = [
    "In the matter of Raga Securities and Finance Private Limited.",
    "The Adjudicating Officer examined the trading records of the broker for the period in detail.",
    "The broker had executed several trades for its clients without keeping proper records of the orders.",
    "Raga Securities and Finance Private Limited was heard through its representative on the matter.",
    "I hereby impose a penalty of Rs. 4,00,000/- on Raga Securities and Finance Private Limited under "
    "section 15HB of the SEBI Act.",
    "The penalty shall be paid within forty five days from the receipt of this order by the broker.",
    "A copy of this order is being sent to the recognised stock exchanges for their records and action.",
]
BODY = FILLER + " " + " ".join(CORE)


def _doc(db, n, doc_type="SEBI adjudication order", year=2024, ocr=False):
    text = BODY
    doc = Document(
        source_kind="SEBI", title=f"Order {n} in the matter of Raga Securities and Finance Private Limited",
        raw_sha256=f"{n:064d}", clean_text=text, status="parsed", doc_type=doc_type,
        published_at=date(year, 3, 1), ocr_used=ocr,
    )  # fmt: skip
    db.add(doc)
    db.flush()
    sents = []
    for i, sp in enumerate(split_sentences(text)):
        s = Sentence(doc_id=doc.id, idx=i, char_start=sp.start, char_end=sp.end, text=sp.slice(text))
        db.add(s)
        sents.append(s)
    db.flush()
    return doc, sents


def _entity(db):
    ent = db.scalar(select(Entity).where(Entity.slug == "raga-securities"))
    if ent is None:
        ent = Entity(slug="raga-securities", canonical_name="Raga Securities and Finance Private Limited")
        db.add(ent)
        db.flush()
    return ent


def _mentions(db, doc, ent):
    name = "Raga Securities and Finance Private Limited"
    pos = 0
    while (at := doc.clean_text.find(name, pos)) >= 0:
        db.add(Mention(doc_id=doc.id, entity_id=ent.id, char_start=at, char_end=at + len(name), surface=name,
                       ner_model="t"))  # fmt: skip
        pos = at + len(name)
    db.flush()


def test_selection_freezes_exact_passages_in_strata_with_a_calibration_set(db):
    docs = [_doc(db, i, year=2015 + i)[0] for i in range(1, 7)]
    docs.append(_doc(db, 9, doc_type="NCLT admission order", ocr=True)[0])
    for d in docs:
        extract_for_document(db, d)
    stats = select_passages(
        db, {"SEBI adjudication order": 4, "NCLT admission order": 2}, calibration=2, seed=1
    )
    passages = list(db.scalars(select(GoldPassage)))
    assert stats.selected == len(passages) == 5 and stats.short_of_quota == {"NCLT admission order": 1}
    for p in passages:
        doc = db.get(Document, p.doc_id)
        assert doc.clean_text[p.char_start : p.char_end] == p.text and len(p.text) >= 250
        assert len(p.text_sha256) == 64
    assert sum(p.role == "calibration" for p in passages) == 2
    assert any(p.has_rule_event for p in passages) and any(not p.has_rule_event for p in passages)
    assert {p.ocr for p in passages if p.stratum == "NCLT admission order"} == {True}
    again = select_passages(db, {"SEBI adjudication order": 4}, calibration=0, seed=1)
    assert again.selected == 0 and again.existing >= 1  # re-running never changes a frozen passage


def test_label_config_lists_every_event_type_and_tasks_carry_the_frozen_text(db):
    root = ET.fromstring(label_config())
    values = {el.get("value") for el in root.iter("Label")}
    assert {"SEBI Penalty", "NCLT Admission", "Stock Split", "Entity"} <= values and len(values) == 17
    doc, _ = _doc(db, 1)
    extract_for_document(db, doc)
    select_passages(db, {"SEBI adjudication order": 1}, calibration=0)
    (task,) = tasks(db)
    assert task["data"]["text"].startswith("In the matter") or len(task["data"]["text"]) > 200
    assert task["data"]["source"] == "SEBI" and len(task["data"]["sha256"]) == 64


def _passage(db):
    doc, _ = _doc(db, 1)
    extract_for_document(db, doc)
    select_passages(db, {"SEBI adjudication order": 1}, calibration=1)
    return doc, db.scalar(select(GoldPassage))


def _region(rid, kind, name, **value):
    return {"id": rid, "type": kind, "from_name": name, "value": value}


def _export(passage, *, sentiment="negative", annotator=7, name_text=None):
    name = "Raga Securities and Finance Private Limited"
    s = passage.text.index(name)
    trig = passage.text.index("I hereby impose")
    trig_end = passage.text.index("SEBI Act.") + len("SEBI Act.")
    result = [
        _region("r1", "labels", "entity", start=s, end=s + len(name), text=name_text or name,
                labels=["Entity"]),
        _region("r1", "choices", "sentiment", choices=[sentiment]),
        _region("r1", "textarea", "slug", text=["raga-securities"]),
        _region("r2", "labels", "event", start=trig, end=trig_end, text=passage.text[trig:trig_end],
                labels=["SEBI Penalty"]),
        _region("r2", "textarea", "event_args", text=["action=penalty; amount_inr=Rs. 4,00,000/-"]),
    ]  # fmt: skip
    task = {"data": {"passage_id": passage.id, "text": passage.text}}
    return [{**task, "annotations": [{"completed_by": annotator, "result": result}]}]


def test_label_studio_import_converts_offsets_and_is_idempotent(db):
    doc, passage = _passage(db)
    export = _export(passage)
    stats = import_export(db, export, {7: "asha"})
    assert (stats.annotations, stats.rows, stats.skipped_spans) == (1, 3, 0)
    ner = db.scalar(select(Annotation).where(Annotation.task == "ner"))
    (span,) = ner.payload["spans"]
    assert (
        doc.clean_text[span["start"] : span["end"]] == span["surface"] and span["entity"] == "raga-securities"
    )
    event = db.scalar(select(Annotation).where(Annotation.task == "event")).payload["events"][0]
    assert event["type"] == "SEBI Penalty" and event["arguments"]["amount_inr"] == "Rs. 4,00,000/-"
    assert doc.clean_text[event["trigger"]["start"] : event["trigger"]["end"]].startswith("I hereby impose")
    assert all(a.label_source == "gold" and a.annotator == "asha" for a in db.scalars(select(Annotation)))
    assert import_export(db, export, {7: "asha"}).rows == 0


def test_a_span_that_does_not_match_the_frozen_text_is_skipped_not_repaired(db):
    _, passage = _passage(db)
    stats = import_export(db, _export(passage, name_text="Some Other Name"), {7: "asha"})
    assert stats.skipped_spans == 1
    assert db.scalar(select(Annotation).where(Annotation.task == "ner")).payload["spans"] == []
    assert import_export(db, [{"data": {"passage_id": 99999}, "annotations": []}], {}).unknown_passages == 1


def test_kappa_span_f1_and_fleiss():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    assert fleiss_kappa([[3, 0], [0, 3], [3, 0]]) == pytest.approx(1.0)
    assert fleiss_kappa([[2, 1], [1, 2], [2, 1], [1, 2]]) < 0.0
    assert (
        span_f1({(0, 3)}, {(0, 3)}) == 1.0
        and span_f1({(0, 3)}, {(4, 6)}) == 0.0
        and span_f1(set(), set()) == 1.0
    )


def test_agreement_is_computed_on_calibration_passages_and_stored(db):
    _, passage = _passage(db)
    import_export(db, _export(passage, sentiment="negative", annotator=1), {1: "asha"})
    import_export(db, _export(passage, sentiment="negative", annotator=2), {2: "ben"})
    rows = {r.task: r for r in compute_agreement(db)}
    assert (
        rows["sentiment"].value == 1.0
        and rows["sentiment"].measure == "cohen_kappa"
        and rows["sentiment"].passed
    )
    assert rows["ner"].value == 1.0 and rows["event"].value == 1.0
    assert db.scalar(select(Agreement).where(Agreement.task == "sentiment")).annotators == "asha,ben"
    assert set(GATES) == {"sentiment", "event", "ner"}


def test_agreement_below_the_gate_fails(db):
    _, passage = _passage(db)
    import_export(db, _export(passage, sentiment="negative", annotator=1), {1: "asha"})
    import_export(db, _export(passage, sentiment="positive", annotator=2), {2: "ben"})
    sentiment = next(r for r in compute_agreement(db) if r.task == "sentiment")
    assert not sentiment.passed


def test_calibration_passages_without_adjudication_are_not_scored(db):
    _, passage = _passage(db)
    import_export(db, _export(passage, annotator=1), {1: "asha"})
    import_export(db, _export(passage, annotator=2), {2: "ben"})
    assert load_gold(db, "event").unadjudicated == 1 and evaluate_events(db, "rules")["n"] == 0
    import_export(db, _export(passage, annotator=3), {3: "adjudicated"})
    assert load_gold(db, "event").unadjudicated == 0 and evaluate_events(db, "rules")["n"] == 1


def test_event_metrics_compare_each_extractor_with_gold(db):
    doc, passage = _passage(db)
    import_export(db, _export(passage, annotator=3), {3: "adjudicated"})
    rules = evaluate_events(db, "rules")
    assert rules["typeF1"] == 1.0 and rules["goldEvents"] == 1.0 and rules["validity"] == 1.0
    assert rules["argF1"] > 0.5  # action and amount agree; the provisions the rule found were not in the gold
    llm = evaluate_events(db, "llm")
    assert llm["typeRecall"] == 0.0 and llm["systemEvents"] == 0.0
    wrong = db.scalar(select(Event).where(Event.doc_id == doc.id))
    wrong.type = "NCLT Admission"
    db.flush()
    assert evaluate_events(db, "rules")["typeF1"] == 0.0


def test_ner_and_link_metrics_and_gold_sentiment_examples(db):
    doc, passage = _passage(db)
    _mentions(db, doc, _entity(db))
    import_export(db, _export(passage, annotator=3), {3: "adjudicated"})
    ner = evaluate_ner(db)
    assert ner["spanRecall"] == 1.0 and ner["linkAcc"] == 1.0 and ner["goldSpans"] == 1.0
    (example,) = sentiment_examples(db)
    assert example.surface == "Raga Securities and Finance Private Limited" and example.label == "negative"
    assert example.text == passage.text and example.dataset == "FinPulse gold"


def test_rouge():
    assert rouge_n("the cat sat", "the cat sat", 1) == 1.0
    assert rouge_n("a b c d", "x y z w", 1) == 0.0
    assert rouge_l("a b c d", "a x c d") == pytest.approx(0.75)
    assert set(rouge("alpha beta", "alpha beta")) == {"rouge1", "rouge2", "rougeL"}


def test_summary_evaluation_scores_the_llm_and_both_baselines_against_a_reference(db):
    _, passage = _passage(db)

    class Llm:
        def chat(self, model, system, user, *, schema=None, num_predict=1024):
            body = {
                "claims": [
                    {"text": "SEBI imposed a penalty of Rs. 400000 on Raga Securities.", "sources": [3]}
                ]
            }
            return Reply(json.dumps(body), model, 100, 20, 1.0)

    added = import_references(
        db,
        [{"passage_id": passage.id, "annotator": "asha",
          "claims": [{"text": "SEBI imposed a penalty of Rs. 400000 on Raga Securities.", "sources": [3]}]}],
    )  # fmt: skip
    assert (
        added == 1
        and import_references(
            db, [{"passage_id": passage.id, "annotator": "asha", "claims": [{"text": "x"}]}]
        )
        == 0
    )
    scores = evaluate_summaries(db, Llm(), "llama", FakeJudge())
    assert scores["llm"]["n"] == 1.0 and scores["llm"]["rougeL"] > 0.8 and scores["llm"]["citationF1"] == 1.0
    assert 0.0 <= scores["llm"]["attribution"] <= 1.0 and scores["llm"]["unsupported"] == pytest.approx(
        1 - scores["llm"]["attribution"]
    )
    assert scores["lead3"]["n"] == scores["lexrank"]["n"] == 1.0
