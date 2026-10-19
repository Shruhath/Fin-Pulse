"""Embedding stage: bge-m3 vectors for every sentence, stored in pgvector for dense retrieval."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finpulse.db.models import EMBEDDING_DIM, Document, Sentence

from .runs import recorded_run

log = logging.getLogger(__name__)
CHUNK = 512


class Encoder(Protocol):
    name: str
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray: ...


@dataclass(slots=True)
class EmbedStats:
    sentences: int = 0


def embed_pending(
    session: Session, encoder: Encoder, *, doc_ids: list[int] | None = None, limit: int | None = None
) -> EmbedStats:
    """Embed sentences that have no vector yet (restricted to some documents when `doc_ids` is given)."""
    if encoder.dim != EMBEDDING_DIM:
        raise ValueError(f"the encoder has {encoder.dim} dimensions, the database column has {EMBEDDING_DIM}")
    stmt = (
        select(Sentence.id, Sentence.text)
        .join(Document, Document.id == Sentence.doc_id)
        .where(Sentence.embedding.is_(None), Document.status.in_(("parsed", "analysed")))
        .order_by(Sentence.id)
    )
    if doc_ids is not None:
        stmt = stmt.where(Sentence.doc_id.in_(doc_ids))
    if limit:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()
    stats = EmbedStats()
    if not rows:
        return stats
    with recorded_run(session, "embed", model=encoder.name, params={"sentences": len(rows)}):
        for lo in range(0, len(rows), CHUNK):
            chunk = rows[lo : lo + CHUNK]
            vectors = encoder.encode([text for _, text in chunk])
            session.execute(
                update(Sentence),
                [
                    {"id": sid, "embedding": vec.tolist()}
                    for (sid, _), vec in zip(chunk, vectors, strict=True)
                ],
            )
            session.commit()
            stats.sentences += len(chunk)
            log.info("embedded %d / %d sentences", stats.sentences, len(rows))
    return stats
