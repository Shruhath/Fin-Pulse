"""Run records: every stage execution is logged, which is the evidence behind stored predictions."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from finpulse.db.models import Run


@contextmanager
def recorded_run(
    session: Session,
    stage: str,
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    params: dict[str, Any] | None = None,
) -> Iterator[Run]:
    """Open a `runs` row, and close it as done or failed with its latency."""
    started = datetime.now(UTC)
    run = Run(stage=stage, model=model, prompt_version=prompt_version, params=params or {}, status="running")
    session.add(run)
    session.flush()
    t0 = time.monotonic()
    try:
        yield run
    except BaseException as exc:
        # Whatever the stage did is rolled back, so the failure is recorded in a fresh transaction.
        session.rollback()
        session.add(
            Run(
                stage=stage,
                model=model,
                prompt_version=prompt_version,
                params=params or {},
                started_at=started,
                finished_at=datetime.now(UTC),
                latency_ms=int((time.monotonic() - t0) * 1000),
                status="failed",
                error=f"{type(exc).__name__}: {exc}"[:2000],
            )
        )
        session.commit()
        raise
    run.status = "done"
    run.finished_at = datetime.now(UTC)
    run.latency_ms = int((time.monotonic() - t0) * 1000)
    session.flush()
