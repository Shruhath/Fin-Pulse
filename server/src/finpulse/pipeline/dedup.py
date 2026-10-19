"""Assign each parsed document the id of its near-duplicate cluster."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Document
from finpulse.preprocess.dedup import cluster


def dedup_documents(session: Session, threshold: float = 0.85) -> tuple[int, int]:
    """Cluster every parsed document. Returns (documents, documents that duplicate an earlier one)."""
    docs = list(session.scalars(select(Document).where(Document.status.in_(("parsed", "analysed")))))
    groups = cluster({d.id: d.clean_text for d in docs}, threshold)
    duplicates = 0
    for d in docs:
        d.minhash_cluster = groups[d.id]
        duplicates += groups[d.id] != d.id
    session.flush()
    return len(docs), duplicates
