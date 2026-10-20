import json

import pytest
from sqlalchemy import select

from finpulse.core.settings import get_settings
from finpulse.db.models import EvalResult, Run
from finpulse.eval.sentiment import train_and_evaluate
from finpulse.pipeline.sentiment import load_scoring_model
from finpulse.sentiment.data import split_of

pytestmark = pytest.mark.db

POS = ["{} jumped on record profit and strong order wins", "{} surged after a big dividend hike announced"]
NEG = [
    "{} slumped after a fraud probe and a heavy penalty",
    "{} plunged on weak results and a rating downgrade",
]
NEU = ["{} announced a board meeting date for next week", "{} appointed a new company secretary on Monday"]


def _benchmarks(root, n=200):
    """Small FinEntity-shaped and SEntFiN-shaped files, large enough that every split has examples."""
    items, rows = [], ["S No.,Title,Decisions,Words"]
    for i in range(n):
        for label, frames in (("positive", POS), ("negative", NEG), ("neutral", NEU)):
            name = f"Firm{i}"
            text = frames[i % 2].format(name)
            items.append(
                {
                    "content": text,
                    "annotations": [{"start": 0, "end": len(name), "tag": label.title(), "value": name}],
                }
            )
            rows.append(f"{i},{frames[(i + 1) % 2].format(name + 'X')},\"{{'{name}X': '{label}'}}\",8")
    (root / "finentity").mkdir(parents=True)
    (root / "finentity" / "FinEntity.json").write_text(json.dumps(items))
    (root / "sentfin").mkdir()
    (root / "sentfin" / "SEntFiN.csv").write_text("\n".join(rows))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    bench = tmp_path / "bench"
    _benchmarks(bench)
    cfg = get_settings()
    monkeypatch.setattr(cfg, "data_dir", tmp_path / "data")
    monkeypatch.setattr(type(cfg), "results_dir", property(lambda self: tmp_path / "results"))
    return bench, tmp_path


def test_every_split_of_the_toy_benchmarks_has_examples():
    assert {split_of(f"text {i}") for i in range(200)} == {"train", "dev", "test"}


def test_the_tfidf_run_records_rows_a_result_file_and_a_loadable_model(db, workspace):
    bench, _ = workspace
    run = train_and_evaluate(db, bench, kind="tfidf")
    assert run.version.startswith("tfidf-lr@") and run.model_path.is_file()
    datasets = {r["dataset"] for r in run.rows}
    assert datasets == {"FinEntity test", "SEntFiN test"}
    rows = list(db.scalars(select(EvalResult).where(EvalResult.stage == "sentiment")))
    assert {r.dataset for r in rows} == datasets and all(r.baseline and r.git_sha for r in rows)
    assert {r.indian for r in rows} == {True, False}
    assert all(
        0.0 <= r.metrics["macroF1"] <= 1.0 and "ece" in r.metrics and r.detail["confusion"] for r in rows
    )
    assert all(len(r.data_hash) == 64 for r in rows)

    saved = json.loads(run.result_path.read_text())
    assert saved["version"] == run.version and saved["train_examples"] > 0 and len(saved["rows"]) == 2
    assert db.scalar(select(Run).where(Run.stage == "sentiment-train")).status == "done"

    model = load_scoring_model()
    assert model is not None and model.version == run.version
    assert load_scoring_model() is model  # kept for the life of the process, not reloaded per call
    probs = model.predict_spans([("Firm9 slumped after a fraud probe and a heavy penalty", 0, 5)])
    assert probs.shape == (1, 3) and probs[0].argmax() == 0  # negative


def test_training_without_benchmark_data_says_how_to_get_it(db, tmp_path):
    with pytest.raises(RuntimeError, match="fetch_layer1"):
        train_and_evaluate(db, tmp_path, kind="tfidf")


def test_an_unknown_model_kind_is_rejected(db, tmp_path):
    bench = tmp_path / "b"
    _benchmarks(bench, 30)
    with pytest.raises(ValueError, match="unknown model kind"):
        train_and_evaluate(db, bench, kind="gpt")
