import pytest
from sqlalchemy import select

from finpulse.db.models import Entity, Run
from finpulse.pipeline.runs import recorded_run

pytestmark = pytest.mark.db


def test_successful_run_is_closed_with_latency(db):
    with recorded_run(db, "parse", model="m", params={"documents": 3}) as run:
        assert run.status == "running"
    stored = db.get(Run, run.id)
    assert stored.status == "done" and stored.latency_ms >= 0 and stored.finished_at is not None


def test_failed_run_is_recorded_and_its_work_rolled_back(db):
    with pytest.raises(RuntimeError, match="boom"), recorded_run(db, "entities") as run:
        db.add(Entity(slug="half-done", canonical_name="Half Done"))
        db.flush()
        raise RuntimeError("boom")
    assert db.scalar(select(Entity).where(Entity.slug == "half-done")) is None
    failed = db.scalars(select(Run).where(Run.stage == "entities", Run.status == "failed")).one()
    assert "RuntimeError: boom" in failed.error
    assert run.id != failed.id  # the in-flight row went with the rollback; the failure was written afresh
