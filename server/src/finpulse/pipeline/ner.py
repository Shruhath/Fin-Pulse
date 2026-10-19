"""NER stage: find company names the gazetteer does not know and link them when they resolve.

The trained model proposes spans in each sentence. A span that overlaps an existing mention is skipped;
the rest become mentions with `ner_model` set to the model version, linked by the resolver (normalised
alias, then fuzzy) or left unresolved. Nothing is created in the gazetteer here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.offsets import Span
from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Mention, Sentence
from finpulse.entities.resolver import Resolver

from .runs import recorded_run

log = logging.getLogger(__name__)
MIN_SCORE = 0.6
BATCH = 256


class SpanModel(Protocol):
    version: str | None

    def predict_batch(self, texts: Sequence[str]) -> list[list[tuple[int, int, float]]]: ...


@dataclass(slots=True)
class NerStats:
    sentences: int = 0
    mentions: int = 0
    linked: int = 0


def load_ner_model(*, device: str = "auto"):
    """The newest trained NER model on disk (transformer preferred over CRF), or None."""
    models = get_settings().models_dir
    transformer = sorted(
        (models / "ner-transformer").glob("*/finpulse.json"), key=lambda p: p.stat().st_mtime
    )
    if transformer:
        from finpulse.ner.transformer import TransformerNer

        return TransformerNer.load(transformer[-1].parent, device=device)
    crf = sorted((models / "ner").glob("*.joblib"), key=lambda p: p.stat().st_mtime)
    if crf:
        from finpulse.ner.crf import CrfNer

        return CrfNer.load(crf[-1])
    return None


def ner_pending(session: Session, model, *, limit: int | None = None) -> NerStats:
    """Run the model over parsed documents that this model version has not processed yet."""
    done = select(Mention.doc_id).where(Mention.ner_model == model.version)
    stmt = (
        select(Document)
        .where(Document.status.in_(("parsed", "analysed")), Document.id.not_in(done))
        .order_by(Document.id)
    )
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = NerStats()
    if not docs:
        return stats
    resolver = Resolver.from_session(session)
    with recorded_run(session, "ner", model=model.version, params={"documents": len(docs)}):
        for doc in docs:
            sentences = list(
                session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
            )
            existing = [
                Span(m.char_start, m.char_end)
                for m in session.scalars(select(Mention).where(Mention.doc_id == doc.id))
            ]
            for lo in range(0, len(sentences), BATCH):
                chunk = sentences[lo : lo + BATCH]
                for sentence, found in zip(chunk, model.predict_batch([s.text for s in chunk]), strict=True):
                    stats.sentences += 1
                    for start, end, score in found:
                        span = Span(sentence.char_start + start, sentence.char_start + end)
                        if score < MIN_SCORE or any(span.overlaps(e) for e in existing):
                            continue
                        res = resolver.resolve(doc.clean_text[span.start : span.end])
                        existing.append(span)
                        session.add(
                            Mention(
                                doc_id=doc.id,
                                sentence_id=sentence.id,
                                entity_id=res.entity_id,
                                char_start=span.start,
                                char_end=span.end,
                                surface=doc.clean_text[span.start : span.end],
                                ner_model=model.version or "ner",
                                ner_score=score,
                                link_method=res.method,
                                link_score=res.score,
                            )
                        )
                        stats.mentions += 1
                        stats.linked += res.entity_id is not None
            session.commit()
    return stats
