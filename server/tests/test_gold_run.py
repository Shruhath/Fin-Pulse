import json

import numpy as np
import pytest
from sqlalchemy import select

from finpulse.core.settings import get_settings
from finpulse.db.models import EvalResult, Run
from finpulse.eval.gold_run import gold_counts, run_gold_eval
from finpulse.gold.labelstudio import import_export
from finpulse.llm.client import Reply
from tests.test_gold import _entity, _export, _mentions, _passage

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(type(get_settings()), "results_dir", property(lambda self: tmp_path / "results"))
    return tmp_path / "results"


class Scorer:
    version = "toy-scorer@1"

    def predict_spans(self, items):
        return np.array([[0.7, 0.2, 0.1]] * len(items))  # always negative


def test_nothing_is_recorded_without_gold_annotations(db):
    assert gold_counts(db) == {}
    run = run_gold_eval(db, scorer=Scorer())
    assert run.rows == [] and run.path is None
    assert db.scalar(select(EvalResult).where(EvalResult.dataset == "FinPulse gold")) is None


def test_each_stage_is_scored_and_recorded_against_the_adjudicated_gold(db, results_dir):
    doc, passage = _passage(db)
    _mentions(db, doc, _entity(db))
    import_export(db, _export(passage, annotator=3), {3: "adjudicated"})
    run = run_gold_eval(db, scorer=Scorer())

    by_stage = {(r["stage"], r["model"]): r for r in run.rows}
    rules = by_stage[("events", "Rules over operative sentences")]
    assert rules["baseline"] and rules["metrics"]["typeF1"] == 1.0
    assert by_stage[("ner", "Gazetteer rules + title parties")]["metrics"]["spanRecall"] == 1.0
    sentiment = by_stage[("sentiment", "toy-scorer@1")]
    assert sentiment["metrics"]["accuracy"] == 1.0 and not sentiment["baseline"]  # the gold label is negative

    stored = list(db.scalars(select(EvalResult).where(EvalResult.dataset == "FinPulse gold")))
    assert len(stored) == len(run.rows) and all(r.indian and r.split == "test" for r in stored)
    saved = json.loads(run.path.read_text())
    assert saved["gold_annotations"] == {"event": 1, "ner": 1, "sentiment": 1} and len(saved["rows"]) == len(
        run.rows
    )
    assert run.path.parent == results_dir / "gold"


def test_the_llm_row_appears_only_when_it_produced_or_was_scored_on_events(db):
    class Llm:
        def chat(self, model, system, user, *, schema=None, num_predict=1024):
            return Reply(
                json.dumps({"claims": [{"text": "SEBI imposed a penalty.", "sources": []}]}), model, 1, 1, 0.1
            )

    _, passage = _passage(db)
    import_export(db, _export(passage, annotator=3), {3: "adjudicated"})
    run = run_gold_eval(db, scorer=None, llm=Llm(), llm_model="llama")
    assert not any(r["stage"] == "sentiment" for r in run.rows)  # no scorer was given
    assert not any("schema-constrained" in r["model"] for r in run.rows)  # the LLM extractor never ran
    assert not any(r["stage"] == "summaries" for r in run.rows)  # no human reference summaries exist

    db.add(Run(stage="events-llm", model="qwen", status="done"))
    db.flush()
    row = next(r for r in run_gold_eval(db).rows if "schema-constrained" in r["model"])
    assert (
        row["metrics"]["typeRecall"] == 0.0 and row["metrics"]["goldEvents"] == 1.0
    )  # it ran and found nothing
