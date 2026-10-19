from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from finpulse.db.models import Document, Job
from finpulse.db.session import get_engine, get_sessionmaker
from finpulse.pipeline import analyze as analyze_mod
from finpulse.pipeline.jobs import enqueue, requeue_stale
from finpulse.pipeline.worker import process_one

pytestmark = pytest.mark.db

ORDER = (
    "In the matter of Raga Securities and Finance Private Limited. I hereby impose a penalty of "
    "Rs. 4,00,000/- on the Noticee viz. Raga Securities and Finance Private Limited under section 15HB of SEBI Act."
)


@pytest.fixture
def committed(migrated_db, monkeypatch):
    """Real, committed sessions (the worker opens its own), cleaned up afterwards."""
    monkeypatch.setattr(analyze_mod, "_llm_client", lambda: None)
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    yield get_sessionmaker()
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "TRUNCATE jobs, claims, summaries, events, mention_sentiment, mentions, sentences, "
                "documents, entity_aliases, entities, runs RESTART IDENTITY CASCADE"
            )
        )


def _queue(factory, kind="analyze"):
    with factory() as s:
        doc = Document(
            source_kind="SEBI",
            title="Order against Raga",
            raw_sha256="a" * 64,
            clean_text="",
            status="ingested",
            doc_type="SEBI adjudication order",
            meta={"origin": "analyze-text", "text": ORDER},
        )
        s.add(doc)
        s.flush()
        job = enqueue(s, kind, {"source": "SEBI"}, document_id=doc.id)
        s.commit()
        return job.id


def test_the_worker_runs_the_oldest_job_to_completion_and_reports_an_empty_queue(committed):
    job_id = _queue(committed)
    assert process_one() is True
    with committed() as s:
        job = s.get(Job, job_id)
        assert job.status == "done" and job.finished_at is not None and job.attempts == 1
        stages = {st["key"]: st["status"] for st in job.stages}
        assert stages["parse"] == "done" and stages["entities"] == "done" and stages["events"] == "done"
        assert s.get(Document, job.document_id).status == "analysed"
    assert process_one() is False


def test_an_unknown_job_kind_is_retried_once_then_marked_failed(committed):
    job_id = _queue(committed, kind="mystery")
    assert process_one() is True  # attempt 1 fails and the job goes back to the queue
    with committed() as s:
        assert s.get(Job, job_id).status == "queued"
    assert process_one() is True  # attempt 2 fails for good
    with committed() as s:
        job = s.get(Job, job_id)
        assert job.status == "failed" and "unknown job kind" in job.error and job.attempts == 2
    assert process_one() is False


def test_jobs_a_dead_worker_left_running_are_requeued(committed):
    job_id = _queue(committed)
    with committed() as s:
        job = s.get(Job, job_id)
        job.status, job.started_at = "running", datetime.now(UTC) - timedelta(hours=1)
        s.commit()
        assert requeue_stale(s) == 1
        assert s.get(Job, job_id).status == "queued"
        job = s.get(Job, job_id)
        job.status, job.started_at = "running", datetime.now(UTC)  # a job that just started is left alone
        s.commit()
        assert requeue_stale(s) == 0
