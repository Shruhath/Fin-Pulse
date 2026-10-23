import numpy as np
import pytest

from finpulse.db.models import Document, EvalResult, Event
from finpulse.eval.components import (
    ASR_DATASET,
    EVENTS_DATASET,
    load_contradiction_pairs,
    record_components,
    score_events,
    score_nli,
)

pytestmark = pytest.mark.db


class _Nli:
    """Says entailment when the two passages are identical, contradiction otherwise."""

    def predict(self, pairs):
        return np.array([[0.95, 0.03, 0.02] if a == b else [0.02, 0.08, 0.9] for a, b in pairs])


def test_nli_scores_same_and_different_pairs_and_beats_the_always_different_baseline():
    pairs = [("a b", "a b", True), ("a b", "a c", False), ("x", "y", False), ("same", "same", True)]
    scores = score_nli(_Nli(), pairs)
    assert scores["nli"]["accuracy"] == 1.0 and scores["nli"]["macroF1"] == 1.0
    assert scores["always-different"]["accuracy"] == 0.5 and scores["always-different"]["recallSame"] == 0.0
    assert scores["always-different"]["macroF1"] < scores["nli"]["macroF1"]


def test_the_contradiction_items_are_read_from_the_benchmark_when_it_is_present(tmp_path):
    assert load_contradiction_pairs(tmp_path) == []  # no benchmark folder: nothing to score, no crash


def _doc(db, sha):
    d = Document(source_kind="SEBI", title="t", raw_sha256=sha * 64, clean_text="x", status="analysed")
    db.add(d)
    db.flush()
    return d


def test_event_agreement_counts_documents_where_both_extractors_ran_and_schema_validity(db):
    a, b = _doc(db, "a"), _doc(db, "b")
    for doc, extractor, kind, amount, valid in (
        (a, "rules", "SEBI Penalty", 500000, None),
        (a, "llm", "SEBI Penalty", 500000, True),
        (a, "llm", "Acquisition", None, True),
        (b, "llm", "NCLT Admission", None, False),
    ):
        db.add(Event(doc_id=doc.id, type=kind, extractor=extractor, amount_inr=amount, schema_valid=valid,
                     trigger_start=0, trigger_end=1, arguments={}))  # fmt: skip
    db.flush()
    llm = score_events(db)["llm"]
    assert llm["n"] == 3 and llm["schemaValid"] == pytest.approx(2 / 3)
    assert llm["agreeRecall"] == 1.0 and llm["agreePrecision"] == 0.5 and llm["amountMatch"] == 1.0


def test_recording_replaces_earlier_rows_and_stores_the_speech_measurement(db, tmp_path):
    for _ in range(2):  # twice: the second run replaces the first
        record_components(db, None, tmp_path)
    rows = db.query(EvalResult).filter(EvalResult.dataset == ASR_DATASET).all()
    assert sorted((r.baseline, r.metrics["wer"]) for r in rows) == [(False, 0.035), (True, 0.205)]
    assert (
        db.query(EvalResult).filter(EvalResult.dataset == EVENTS_DATASET).count() == 0
    )  # no events, no rows
