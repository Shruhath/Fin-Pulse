"""Postgres-backed job queue.

One GPU means one worker, so a table with `FOR UPDATE SKIP LOCKED` gives retries and status
for `/jobs/{id}` without a broker. Stage progress is stored on the job row for the UI to poll.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Job

STAGE_KEYS = ("ingest", "parse", "entities", "sentiment", "events", "summary", "verify")
STAGES_BY_KIND = {"analyze": STAGE_KEYS, "ask": ("retrieve", "answer", "verify")}
STALE_AFTER = timedelta(minutes=20)


def new_stages(kind: str = "analyze") -> list[dict[str, Any]]:
    return [
        {"key": k, "status": "pending", "ms": None, "note": None}
        for k in STAGES_BY_KIND.get(kind, STAGE_KEYS)
    ]


def enqueue(session: Session, kind: str, payload: dict[str, Any], *, document_id: int | None = None) -> Job:
    job = Job(kind=kind, payload=payload, stages=new_stages(kind), document_id=document_id)
    session.add(job)
    session.flush()
    return job


def claim_next(session: Session) -> Job | None:
    """Take the oldest queued job for this worker. Commits the claim so other sessions see it."""
    job = session.scalar(
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    session.commit()
    return job


def set_stage(
    session: Session, job: Job, key: str, status: str, *, ms: int | None = None, note: str | None = None
) -> None:
    job.stages = [
        {**stage, "status": status, "ms": ms, "note": note} if stage["key"] == key else stage
        for stage in job.stages
    ]
    session.commit()


def finish(session: Session, job: Job, *, error: str | None = None) -> None:
    """Close a job. A failed job with attempts left goes back to the queue."""
    if error is None:
        job.status = "done"
    elif job.attempts < job.max_attempts:
        job.status = "queued"
        job.stages = new_stages(job.kind)
        job.error = error
        session.commit()
        return
    else:
        job.status = "failed"
        job.stages = [
            {**s, "status": "failed", "note": error[:200]} if s["status"] == "running" else s
            for s in job.stages
        ]
    job.error = error
    job.finished_at = datetime.now(UTC)
    session.commit()


def requeue_stale(session: Session) -> int:
    """Jobs a crashed worker left 'running' go back to the queue."""
    cutoff = datetime.now(UTC) - STALE_AFTER
    stale = list(session.scalars(select(Job).where(Job.status == "running", Job.started_at < cutoff)))
    for job in stale:
        job.status, job.stages = "queued", new_stages(job.kind)
    session.commit()
    return len(stale)


def get_job(session: Session, job_id: str) -> Job | None:
    try:
        return session.get(Job, uuid.UUID(job_id))
    except ValueError:
        return None
