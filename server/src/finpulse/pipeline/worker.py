"""The queue worker: one process, one job at a time."""

from __future__ import annotations

import logging
import time

from finpulse.db.session import get_sessionmaker

from .analyze import run_analysis
from .ask import run_ask
from .jobs import claim_next, finish, requeue_stale

log = logging.getLogger(__name__)


def process_one() -> bool:
    """Run the oldest queued job. Returns False when the queue is empty."""
    session = get_sessionmaker()()
    try:
        job = claim_next(session)
        if job is None:
            return False
        log.info("job %s started (%s)", job.id, job.kind)
        try:
            if job.kind == "analyze":
                run_analysis(session, job)
            elif job.kind == "ask":
                run_ask(session, job)
            else:
                raise ValueError(f"unknown job kind {job.kind!r}")
        except Exception as exc:
            log.exception("job %s failed", job.id)
            session.rollback()
            finish(session, job, error=f"{type(exc).__name__}: {exc}"[:500])
        else:
            log.info("job %s finished: %s", job.id, job.status)
        return True
    finally:
        session.close()


def run_worker(*, poll_seconds: float = 2.0, once: bool = False) -> None:
    session = get_sessionmaker()()
    try:
        recovered = requeue_stale(session)
    finally:
        session.close()
    if recovered:
        log.warning("requeued %d job(s) left running by a previous worker", recovered)
    while True:
        busy = process_one()
        if once and not busy:
            return
        if not busy:
            time.sleep(poll_seconds)
