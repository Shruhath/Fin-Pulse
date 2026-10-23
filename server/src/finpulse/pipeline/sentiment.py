"""Sentiment stage: score every linked mention with the trained baseline.

Each prediction is stored under the model version that made it, so several models can sit side
by side. The baseline's confidence is its raw softmax maximum (not calibrated), and the version
string says which model produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Mention, MentionSentiment
from finpulse.sentiment.baseline import SentimentBaseline, window_text
from finpulse.sentiment.data import LABELS

from .runs import recorded_run

BATCH = 2000


@dataclass(slots=True)
class SentimentStats:
    mentions: int = 0
    version: str = ""


def latest_model_path(directory: Path | None = None) -> Path | None:
    directory = directory or get_settings().models_dir / "sentiment"
    files = sorted(directory.glob("*.joblib"), key=lambda p: p.stat().st_mtime) if directory.is_dir() else []
    return files[-1] if files else None


def score_pending(
    session: Session, model: SentimentBaseline, *, limit: int | None = None, doc_id: int | None = None
) -> SentimentStats:
    """Score linked mentions that have no prediction from this model version yet."""
    assert model.version is not None
    scored = select(MentionSentiment.mention_id).where(MentionSentiment.model_version == model.version)
    stmt = (
        select(Mention, Document.clean_text)
        .join(Document, Document.id == Mention.doc_id)
        .where(Mention.entity_id.is_not(None), Mention.id.not_in(scored))
        .order_by(Mention.id)
    )
    if doc_id is not None:
        stmt = stmt.where(Mention.doc_id == doc_id)
    if limit:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()
    stats = SentimentStats(version=model.version)
    if not rows:
        return stats
    with recorded_run(session, "sentiment", model=model.version, params={"mentions": len(rows)}):
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            windows = [window_text(text, m.char_start, m.char_end) for m, text in chunk]
            probs = model.predict_proba(windows)
            for (mention, _), p in zip(chunk, probs, strict=True):
                neg, neu, pos = (float(x) for x in p)
                session.add(
                    MentionSentiment(
                        mention_id=mention.id,
                        model_version=model.version,
                        label=LABELS[int(p.argmax())],
                        p_pos=pos,
                        p_neg=neg,
                        p_neu=neu,
                        confidence=max(neg, neu, pos),
                    )
                )
            session.flush()
            stats.mentions += len(chunk)
    return stats
