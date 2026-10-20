"""Choose the passages annotators will label, and freeze them.

A passage is a run of up to five consecutive sentences, so every span in it is an exact slice of
`documents.clean_text`. Passages are drawn per stratum (document type) with a fixed quota, spread
across years, and half of them are built around a sentence where the rule baseline found an event
and half around ordinary mention-dense text, so recall is measured on documents with and without
events. The text is stored with its SHA-256 and OCR provenance: once selected it never changes.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Event, GoldPassage, Mention, Sentence
from finpulse.parse.ocr import tesseract_version
from finpulse.summarize.prune import usable

MIN_CHARS = 250
MAX_CHARS = 1600
MAX_SENTENCES = 5
DEFAULT_QUOTAS = {
    "SEBI adjudication order": 40,
    "SEBI whole-time member order": 15,
    "SEBI settlement order": 15,
    "NCLT admission order": 50,
}


@dataclass(slots=True)
class SelectStats:
    selected: int = 0
    existing: int = 0
    short_of_quota: dict[str, int] | None = None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_passage(sentences: list[Sentence], anchor: int) -> tuple[int, int] | None:
    """The span (start, end) of a passage around sentence `anchor`, or None when the text is not usable."""
    lo, hi = anchor, anchor
    while hi - lo + 1 < MAX_SENTENCES:
        grew = False
        if hi + 1 < len(sentences) and sentences[hi + 1].char_end - sentences[lo].char_start <= MAX_CHARS:
            hi += 1
            grew = True
        if (
            hi - lo + 1 < MAX_SENTENCES
            and lo > 0
            and sentences[hi].char_end - sentences[lo - 1].char_start <= MAX_CHARS
        ):
            lo -= 1
            grew = True
        if not grew:
            break
    start, end = sentences[lo].char_start, sentences[hi].char_end
    body = [s for s in sentences[lo : hi + 1] if usable(s.text)]
    if end - start < MIN_CHARS or len(body) < max(2, (hi - lo + 1) // 2):
        return None
    return start, end


def _anchor_for(
    sentences: list[Sentence],
    triggers: list[tuple[int, int]],
    mention_counts: dict[int, int],
    want_event: bool,
) -> int | None:
    if want_event and triggers:
        t0, t1 = triggers[0]
        for i, s in enumerate(sentences):
            if s.char_start < t1 and t0 < s.char_end:
                return i
    in_trigger = lambda s: any(s.char_start < t1 and t0 < s.char_end for t0, t1 in triggers)  # noqa: E731
    plain = [
        (mention_counts.get(s.id, 0), i)
        for i, s in enumerate(sentences)
        if usable(s.text) and not in_trigger(s)
    ]
    if not plain:
        return None
    best = max(plain)[0]
    return min(i for c, i in plain if c == best) if best else plain[len(plain) // 2][1]


def select_passages(
    session: Session,
    quotas: dict[str, int] | None = None,
    *,
    calibration: int = 30,
    seed: int = 7,
) -> SelectStats:
    quotas = quotas or DEFAULT_QUOTAS
    rng = random.Random(seed)
    cfg = get_settings()
    engine = f"tesseract {tesseract_version() or 'unknown'}"
    stats = SelectStats(short_of_quota={})
    chosen: list[GoldPassage] = []

    for doc_type, quota in quotas.items():
        docs = list(
            session.scalars(
                select(Document)
                .where(Document.doc_type == doc_type, Document.status.in_(("parsed", "analysed")))
                .order_by(Document.id)
            )
        )
        by_year: dict[int, list[Document]] = defaultdict(list)
        for d in docs:
            by_year[d.published_at.year if d.published_at else 0].append(d)
        for group in by_year.values():
            rng.shuffle(group)
        order: list[Document] = []
        while any(by_year.values()):  # one document per year in turn, so the quota spans the years
            for year in sorted(by_year):
                if by_year[year]:
                    order.append(by_year[year].pop())

        made = 0
        for doc in order:
            if made >= quota:
                break
            sentences = list(
                session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
            )
            triggers = [
                (e.trigger_start, e.trigger_end)
                for e in session.scalars(
                    select(Event).where(Event.doc_id == doc.id, Event.extractor == "rules")
                )
                if e.trigger_start is not None
            ]
            counts = dict(
                session.execute(
                    select(Mention.sentence_id, func.count())
                    .where(Mention.doc_id == doc.id)
                    .group_by(Mention.sentence_id)
                ).all()
            )
            want_event = made % 2 == 0
            anchor = _anchor_for(sentences, triggers, counts, want_event)
            if anchor is None and want_event:
                anchor = _anchor_for(sentences, triggers, counts, False)
            span = build_passage(sentences, anchor) if anchor is not None else None
            if span is None:
                continue
            existing = session.scalar(
                select(GoldPassage).where(
                    GoldPassage.doc_id == doc.id,
                    GoldPassage.char_start == span[0],
                    GoldPassage.char_end == span[1],
                )
            )
            if existing:
                stats.existing += 1
                made += 1
                continue
            text = doc.clean_text[span[0] : span[1]]
            passage = GoldPassage(
                doc_id=doc.id,
                char_start=span[0],
                char_end=span[1],
                text=text,
                text_sha256=sha256(text),
                stratum=doc_type,
                has_rule_event=any(span[0] < t1 and t0 < span[1] for t0, t1 in triggers),
                role="gold",
                ocr=doc.ocr_used,
                ocr_engine=engine if doc.ocr_used else None,
                ocr_dpi=cfg.ocr_dpi if doc.ocr_used else None,
            )
            session.add(passage)
            chosen.append(passage)
            made += 1
            stats.selected += 1
        if made < quota:
            stats.short_of_quota[doc_type] = quota - made  # type: ignore[index]
    session.flush()

    # the shared calibration set takes passages in turn from every stratum
    pools = defaultdict(list)
    for p in chosen:
        pools[p.stratum].append(p)
    picked = 0
    while picked < calibration and any(pools.values()):
        for stratum in sorted(pools):
            if pools[stratum] and picked < calibration:
                pools[stratum].pop().role = "calibration"
                picked += 1
    session.flush()
    return stats
