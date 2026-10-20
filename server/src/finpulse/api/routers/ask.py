"""Ask a question of the corpus and follow the answer as it is built."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finpulse.api import queries as q
from finpulse.api import schemas as s
from finpulse.api.deps import get_db
from finpulse.db.models import Document, Entity, Event, Job
from finpulse.pipeline.ask import MAX_QUESTION
from finpulse.pipeline.jobs import enqueue, get_job

from .analyze import MAX_QUEUED

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
MIN_QUESTION = 3

# What the corpus can answer best is what was extracted from it, so the suggestions are built from the
# newest extracted events (real companies, real documents) rather than written by hand.
_SUGGESTIONS = {
    "SEBI Penalty": "What action did SEBI take against {entity}?",
    "NCLT Admission": "Why was {entity} admitted into insolvency resolution?",
    "RBI Action": "What action did the RBI take against {entity}?",
}


@router.get("/ask/suggestions", response_model=list[str])
def suggestions(db: Db, limit: int = 4) -> list[str]:
    rows = db.execute(
        select(Event.type, Entity.canonical_name)
        .join(Entity, Entity.id == Event.entity_id)
        .join(Document, Document.id == Event.doc_id)
        .where(q.IN_CORPUS, Entity.kind.in_(("company", "bank")), Event.type.in_(tuple(_SUGGESTIONS)))
        .order_by(func.coalesce(Event.event_date, Document.published_at).desc().nulls_last(), Event.id.desc())
        .limit(60)
    ).all()
    out: list[str] = []
    seen_types: dict[str, int] = {}
    for event_type, name in rows:
        question = _SUGGESTIONS[event_type].format(entity=name)
        if question in out or seen_types.get(event_type, 0) >= 2:
            continue
        seen_types[event_type] = seen_types.get(event_type, 0) + 1
        out.append(question)
        if len(out) >= limit:
            break
    return out


@router.post("/ask", response_model=s.AskAccepted, status_code=202)
def ask(body: s.AskRequest, db: Db) -> s.AskAccepted:
    """Queue a question. The answer is built by the worker; poll `/ask/{id}` for its progress."""
    question = " ".join(body.question.split())
    if len(question) < MIN_QUESTION:
        raise HTTPException(422, "ask a question of at least a few words")
    if len(question) > MAX_QUESTION:
        raise HTTPException(422, f"keep the question under {MAX_QUESTION} characters")
    waiting = db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0
    if waiting >= MAX_QUEUED:
        raise HTTPException(429, "the queue is full; try again in a few minutes")
    job = enqueue(db, "ask", {"question": question})
    db.commit()
    return s.AskAccepted(job_id=str(job.id))


@router.get("/ask/{job_id}", response_model=s.AskJob)
def ask_job(job_id: str, db: Db) -> s.AskJob:
    row = get_job(db, job_id)
    if row is None or row.kind != "ask":
        raise HTTPException(404, "no such question")
    return s.AskJob(
        id=str(row.id),
        status=row.status,
        stages=[s.AskStage(**stage) for stage in row.stages],
        error=row.error,
        answer=s.AskAnswer.model_validate(row.result) if row.result else None,
    )
