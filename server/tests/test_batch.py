import pytest

from finpulse.llm.client import LlmUnavailable
from finpulse.pipeline import batch
from finpulse.pipeline.batch import DEFAULT_STAGES, STAGES, Skip, run_pipeline


def _runners(monkeypatch, **overrides):
    calls = []

    def make(name):
        def run(**kw):
            calls.append(name)
            return f"{name} ok"

        return run

    table = {name: make(name) for name in STAGES}
    table.update(overrides)
    monkeypatch.setattr(batch, "_RUNNERS", table)
    return calls


def test_stages_run_in_pipeline_order_whatever_order_they_were_asked_for(monkeypatch):
    calls = _runners(monkeypatch)
    results = run_pipeline(("verify", "parse", "events-llm", "link"))
    assert calls == ["parse", "link", "events-llm", "verify"]
    assert [r.status for r in results] == ["done"] * 4 and results[0].note == "parse ok"


def test_the_gpu_phases_never_overlap_the_llm_phases(monkeypatch):
    assert STAGES.index("sentiment") < STAGES.index("embed") < STAGES.index("events-llm")
    assert STAGES.index("events-llm") < STAGES.index("summaries") < STAGES.index("verify")


def test_a_phase_that_cannot_run_is_skipped_with_its_reason_and_the_run_goes_on(monkeypatch):
    def no_gpu(**kw):
        raise Skip("the neural extra is not installed")

    def no_llm(**kw):
        raise LlmUnavailable("no Ollama server")

    calls = _runners(monkeypatch, embed=no_gpu, **{"events-llm": no_llm})
    seen = []
    results = run_pipeline(("embed", "events-llm", "summaries"), report=seen.append)
    assert [(r.stage, r.status) for r in results] == [
        ("embed", "skipped"),
        ("events-llm", "skipped"),
        ("summaries", "done"),
    ]
    assert "neural extra" in results[0].note and "no Ollama" in results[1].note
    assert calls == ["summaries"] and len(seen) == 3


def test_a_failed_phase_stops_the_run_because_later_phases_depend_on_it(monkeypatch):
    def broken(**kw):
        raise RuntimeError("database exploded")

    calls = _runners(monkeypatch, link=broken)
    results = run_pipeline(("parse", "link", "events"))
    assert [r.status for r in results] == ["done", "failed"]
    assert "database exploded" in results[1].note and calls == ["parse"]


def test_unknown_stage_names_are_rejected_up_front(monkeypatch):
    _runners(monkeypatch)
    with pytest.raises(ValueError, match="nonsense"):
        run_pipeline(("parse", "nonsense"))


def test_ner_runs_only_when_asked_for(monkeypatch):
    calls = _runners(monkeypatch)
    run_pipeline()
    assert "ner" not in calls and calls == list(DEFAULT_STAGES)
    calls.clear()
    run_pipeline(("ner",))
    assert calls == ["ner"]
