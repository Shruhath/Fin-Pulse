"""The company names a spoken question is most likely to contain, for the transcriber's prompt."""

from __future__ import annotations

import time

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from finpulse.db.models import Document, Entity, Event, Mention
from finpulse.entities.names import LEGAL_SUFFIXES

RECENT_EVENTS = 25  # companies the suggested questions are built from, so those can be spoken reliably
MOST_MENTIONED = 45
REFRESH_SECONDS = 600

_cache: tuple[float, list[str]] | None = None


def spoken_form(name: str) -> str:
    """How a person says it: no legal suffix, and not in capitals (a capitals prompt invites capitals)."""
    words = name.split()
    while len(words) > 1 and words[-1].lower().strip(".") in LEGAL_SUFFIXES:
        words.pop()
    short = " ".join(words)
    return short.title() if short.isupper() else short


def top_company_names(session: Session) -> list[str]:
    """Companies with the newest extracted events, then those mentioned in the most filings."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < REFRESH_SECONDS:
        return _cache[1]
    corpus = Document.is_submission.is_(False)
    companies = Entity.kind.in_(("company", "bank"))
    recent = session.execute(
        select(Entity.canonical_name)
        .join(Event, Event.entity_id == Entity.id)
        .join(Document, Document.id == Event.doc_id)
        .where(corpus, companies)
        .group_by(Entity.id)
        .order_by(
            desc(func.max(func.coalesce(Event.event_date, Document.published_at))), Entity.canonical_name
        )
        .limit(RECENT_EVENTS)
    ).scalars()
    frequent = session.execute(
        select(Entity.canonical_name)
        .join(Mention, Mention.entity_id == Entity.id)
        .join(Document, Document.id == Mention.doc_id)
        .where(corpus, companies)
        .group_by(Entity.id)
        .order_by(desc(func.count(func.distinct(Mention.doc_id))), Entity.canonical_name)
        .limit(MOST_MENTIONED)
    ).scalars()
    names: list[str] = []
    for full in [*recent, *frequent]:
        short = spoken_form(str(full))
        if short and short not in names:
            names.append(short)
    _cache = (now, names)
    return names
