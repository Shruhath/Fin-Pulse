"""Corpus-wide evidence search for a question: BM25 and dense search fused with reciprocal rank fusion.

This is the retriever the verify stage uses for claims (`verify/`), applied to every sentence of the
collected corpus instead of one document's. When the question names a company, only documents that
mention it are searched; when it names a publisher, only that publisher's documents are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finpulse.db.models import Document, Mention, Sentence
from finpulse.verify.bm25 import BM25, rrf

TOP_K = 8
POOL = 40  # how deep each retriever goes before fusion
IN_CORPUS = Document.is_submission.is_(False)
SEARCHABLE = Document.status.in_(("parsed", "analysed"))


@dataclass(frozen=True, slots=True)
class Passage:
    sentence_id: int
    doc_id: int
    text: str
    char_start: int
    char_end: int
    title: str
    source: str
    published_at: date | None
    rank: int  # 1-based position after fusion


class CorpusIndex:
    """BM25 over every sentence of the corpus, built once and rebuilt when the corpus changes."""

    def __init__(self, session: Session):
        rows = session.execute(
            select(Sentence.id, Sentence.doc_id, Sentence.text)
            .join(Document, Document.id == Sentence.doc_id)
            .where(IN_CORPUS, SEARCHABLE)
            .order_by(Sentence.id)
        ).all()
        self.ids = [r[0] for r in rows]
        self.doc_ids = np.array([r[1] for r in rows], dtype=np.int64)
        self.bm25 = BM25([r[2] for r in rows])
        self.stamp = self.corpus_stamp(session)

    @staticmethod
    def corpus_stamp(session: Session) -> tuple[int, int]:
        """Changes whenever a sentence is added or removed."""
        count, newest = session.execute(
            select(func.count(Sentence.id), func.coalesce(func.max(Sentence.id), 0))
            .join(Document, Document.id == Sentence.doc_id)
            .where(IN_CORPUS, SEARCHABLE)
        ).one()
        return int(count), int(newest)

    def is_current(self, session: Session) -> bool:
        return self.stamp == self.corpus_stamp(session)

    def rank(self, query: str, doc_filter: set[int] | None, k: int = POOL) -> list[int]:
        allowed = None
        if doc_filter is not None:
            allowed = set(np.flatnonzero(np.isin(self.doc_ids, list(doc_filter))).tolist())
        return [self.ids[i] for i in self.bm25.rank(query, k, allowed)]


def documents_for(session: Session, entity_ids: tuple[int, ...], sources: tuple[str, ...]) -> set[int] | None:
    """The documents a question is limited to, or None when it names neither a company nor a publisher."""
    if not entity_ids and not sources:
        return None
    stmt = select(Document.id).where(IN_CORPUS, SEARCHABLE)
    if entity_ids:
        stmt = stmt.where(Document.id.in_(select(Mention.doc_id).where(Mention.entity_id.in_(entity_ids))))
    if sources:
        stmt = stmt.where(Document.source_kind.in_(sources))
    return set(session.scalars(stmt))


def dense_ids(session: Session, vector: np.ndarray, doc_filter: set[int] | None, k: int = POOL) -> list[int]:
    stmt = select(Sentence.id).where(Sentence.embedding.is_not(None))
    if doc_filter is None:
        stmt = stmt.where(Sentence.doc_id.in_(select(Document.id).where(IN_CORPUS, SEARCHABLE)))
    else:
        stmt = stmt.where(Sentence.doc_id.in_(list(doc_filter)))
    stmt = stmt.order_by(Sentence.embedding.cosine_distance(vector.tolist())).limit(k)
    return list(session.scalars(stmt))


def _key(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def retrieve(
    session: Session,
    index: CorpusIndex,
    question: str,
    *,
    vector: np.ndarray | None,
    doc_filter: set[int] | None,
    k: int = TOP_K,
) -> list[Passage]:
    """The k best sentences for the question, best first, one per distinct wording."""
    if doc_filter is not None and not doc_filter:
        return []
    rankings = [index.rank(question, doc_filter)]
    if vector is not None:
        rankings.append(dense_ids(session, vector, doc_filter))
    fused = rrf([r for r in rankings if r])
    if not fused:
        return []
    order = [int(item) for item, _ in fused[: k * 3]]
    rows = {
        s.id: (s, d)
        for s, d in session.execute(
            select(Sentence, Document)
            .join(Document, Document.id == Sentence.doc_id)
            .where(Sentence.id.in_(order))
        )
    }
    passages: list[Passage] = []
    seen: set[str] = set()
    for sid in order:
        if sid not in rows:
            continue
        sentence, doc = rows[sid]
        key = _key(sentence.text)
        if key in seen:  # the same wording in a near-duplicate document adds nothing
            continue
        seen.add(key)
        passages.append(
            Passage(
                sentence_id=sid,
                doc_id=doc.id,
                text=sentence.text,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                title=doc.title,
                source=doc.source_kind,
                published_at=doc.published_at,
                rank=len(passages) + 1,
            )
        )
        if len(passages) == k:
            break
    return passages
