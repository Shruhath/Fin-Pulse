"""The company names a spoken question is most likely to contain, for the transcriber's prompt."""

from __future__ import annotations

import time

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from finpulse.db.models import Document, Entity, Mention

TOP = 30
REFRESH_SECONDS = 600

_cache: tuple[float, list[str]] | None = None


def top_company_names(session: Session, n: int = TOP) -> list[str]:
    """Canonical names of the companies mentioned in the most filings, most mentioned first."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < REFRESH_SECONDS:
        return _cache[1]
    rows = session.execute(
        select(Entity.canonical_name)
        .join(Mention, Mention.entity_id == Entity.id)
        .join(Document, Document.id == Mention.doc_id)
        .where(Entity.kind.in_(("company", "bank")), Document.is_submission.is_(False))
        .group_by(Entity.id)
        .order_by(desc(func.count(func.distinct(Mention.doc_id))), Entity.canonical_name)
        .limit(n)
    ).scalars()
    names = [str(r) for r in rows]
    _cache = (now, names)
    return names
