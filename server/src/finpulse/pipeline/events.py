"""Event stage (rule baseline): operative sentences of SEBI, NCLT and RBI documents -> `events` rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from finpulse.core.offsets import Span
from finpulse.db.models import Document, Event, Mention, Sentence
from finpulse.events.rules import extract_events

from .link import NER_TITLE
from .runs import recorded_run

log = logging.getLogger(__name__)

EXTRACTOR = "rules"


@dataclass(slots=True)
class EventStats:
    documents: int = 0
    events: int = 0
    without_entity: int = 0
    invalid: int = 0


def _subject_entity(session: Session, doc_id: int) -> int | None:
    """The entity the document is about: its first linked title-party mention."""
    return session.scalar(
        select(Mention.entity_id)
        .where(Mention.doc_id == doc_id, Mention.ner_model == NER_TITLE, Mention.entity_id.is_not(None))
        .order_by(Mention.char_start)
        .limit(1)
    )


def extract_for_document(session: Session, doc: Document, run_id: int | None = None) -> int:
    """Replace the rule events of one document. Returns how many were stored."""
    spans = [
        Span(r.char_start, r.char_end)
        for r in session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
    ]
    drafts = extract_events(
        source_kind=doc.source_kind,
        doc_type=doc.doc_type,
        text=doc.clean_text,
        sentence_spans=spans,
        published_at=doc.published_at,
    )
    session.execute(delete(Event).where(Event.doc_id == doc.id, Event.extractor == EXTRACTOR))
    entity_id = _subject_entity(session, doc.id) if drafts else None
    for d in drafts:
        session.add(
            Event(
                doc_id=doc.id,
                entity_id=entity_id,
                type=d.type.value,
                trigger_start=d.trigger.start,
                trigger_end=d.trigger.end,
                arguments=d.arguments,
                event_date=d.event_date,
                amount_inr=d.amount_inr,
                confidence=None,  # a rule is not a probability
                schema_valid=d.schema_valid,
                extractor=EXTRACTOR,
                run_id=run_id,
            )
        )
    session.flush()
    return len(drafts)


def extract_pending(session: Session, *, limit: int | None = None) -> EventStats:
    """Redo the rule events of every parsed SEBI or NCLT document."""
    stmt = (
        select(Document)
        .where(Document.status.in_(("parsed", "analysed")), Document.source_kind.in_(("SEBI", "NCLT", "RBI")))
        .order_by(Document.id)
    )
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = EventStats()
    if not docs:
        return stats
    with recorded_run(session, "events", model="rules-v1", params={"documents": len(docs)}) as run:
        for doc in docs:
            stored = extract_for_document(session, doc, run.id)
            stats.documents += 1
            stats.events += stored
            if stored:
                stats.without_entity += session.scalar(
                    select(func.count())
                    .select_from(Event)
                    .where(Event.doc_id == doc.id, Event.entity_id.is_(None))
                )
                stats.invalid += session.scalar(
                    select(func.count())
                    .select_from(Event)
                    .where(Event.doc_id == doc.id, Event.schema_valid.is_(False))
                )
            session.commit()
    return stats
