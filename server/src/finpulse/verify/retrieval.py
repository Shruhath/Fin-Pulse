"""Find the evidence for a claim: BM25 and dense search over the candidate sentences, fused with RRF."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Claim, Document, Mention, Sentence, Summary

from .bm25 import BM25, rrf

TOP_K = 5
POOL = 20  # how deep each retriever goes before fusion
MAX_CANDIDATES = 20_000


@dataclass(frozen=True, slots=True)
class Hit:
    sentence_id: int
    score: float  # the RRF score
    rank: int  # 1-based position after fusion


def candidate_sentences(session: Session, summary: Summary) -> list[tuple[int, str]]:
    """Sentences a claim may rest on: its own document, or every document that mentions the company."""
    if summary.scope == "document" and summary.doc_id is not None:
        stmt = select(Sentence.id, Sentence.text).where(Sentence.doc_id == summary.doc_id)
    elif summary.entity_id is not None:
        docs = (
            select(Mention.doc_id)
            .join(Document, Document.id == Mention.doc_id)
            .where(Mention.entity_id == summary.entity_id)
        )
        if summary.window_start is not None:
            docs = docs.where(Document.published_at >= summary.window_start)
        if summary.window_end is not None:
            docs = docs.where(Document.published_at <= summary.window_end)
        stmt = select(Sentence.id, Sentence.text).where(Sentence.doc_id.in_(docs.distinct()))
    else:
        return []
    return [(sid, text) for sid, text in session.execute(stmt.order_by(Sentence.id).limit(MAX_CANDIDATES))]


def dense_ranking(
    session: Session, vector: np.ndarray, candidate_ids: Sequence[int], k: int = POOL
) -> list[int]:
    if not candidate_ids:
        return []
    stmt = (
        select(Sentence.id)
        .where(Sentence.id.in_(list(candidate_ids)), Sentence.embedding.is_not(None))
        .order_by(Sentence.embedding.cosine_distance(vector.tolist()))
        .limit(k)
    )
    return list(session.scalars(stmt))


def retrieve(
    session: Session,
    claim: Claim,
    candidates: Sequence[tuple[int, str]],
    *,
    vector: np.ndarray | None = None,
    k: int = TOP_K,
) -> list[Hit]:
    """Top-k evidence sentences for the claim. Dense search is skipped when no embedding is available."""
    if not candidates:
        return []
    ids = [sid for sid, _ in candidates]
    bm25 = BM25([text for _, text in candidates])
    rankings: list[list[int]] = [[ids[i] for i in bm25.rank(claim.text, POOL)]]
    if vector is not None:
        rankings.append(dense_ranking(session, vector, ids))
    fused = rrf([r for r in rankings if r])
    return [Hit(int(item), score, rank) for rank, (item, score) in enumerate(fused[:k], start=1)]
