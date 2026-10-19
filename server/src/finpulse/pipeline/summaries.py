"""Summary stage: Llama writes cited claims for a document or for a company over a window.

Claims are stored unverified, with the evidence sentences the model cited; the verify stage then
retrieves its own evidence and scores each claim with NLI. Re-running replaces the earlier
summary of the same subject.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from finpulse.api.queries import anchor_date, window_start
from finpulse.db.models import Claim, Document, Entity, Event, Mention, Sentence, Summary
from finpulse.llm.client import Llm, LlmError
from finpulse.summarize.llm import PROMPT_VERSION, SummaryResult, summarise
from finpulse.summarize.prune import select as select_sentences

from .runs import recorded_run

log = logging.getLogger(__name__)

EVIDENCE_BUDGET_CHARS = 10_000
ENTITY_EVIDENCE_SENTENCES = 30


@dataclass(slots=True)
class SummaryStats:
    summaries: int = 0
    claims: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    dropped_sources: int = 0


def document_evidence(session: Session, doc: Document) -> list[tuple[int, str]]:
    sentences = list(
        session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
    )
    triggers = [
        (e.trigger_start, e.trigger_end)
        for e in session.scalars(select(Event).where(Event.doc_id == doc.id))
        if e.trigger_start is not None
    ]
    must = [
        i
        for i, s in enumerate(sentences)
        if any(s.char_start < t1 and t0 < s.char_end for t0, t1 in triggers)
    ]
    chosen = select_sentences([s.text for s in sentences], budget_chars=EVIDENCE_BUDGET_CHARS, must_keep=must)
    return [(sentences[i].id, sentences[i].text) for i in chosen]


def entity_evidence(
    session: Session, entity: Entity, start: date | None, end: date | None
) -> list[tuple[int, str]]:
    """The newest sentences that mention the company, plus the sentences that trigger its events."""
    stmt = (
        select(Sentence.id, Sentence.text, Document.published_at)
        .join(Mention, Mention.sentence_id == Sentence.id)
        .join(Document, Document.id == Mention.doc_id)
        .where(Mention.entity_id == entity.id)
    )
    if start is not None:
        stmt = stmt.where(Document.published_at >= start)
    if end is not None:
        stmt = stmt.where(Document.published_at <= end)
    rows = session.execute(stmt.order_by(desc(Document.published_at).nulls_last(), Sentence.id)).all()
    trigger_rows = session.execute(
        select(Sentence.id, Sentence.text)
        .join(Event, (Event.doc_id == Sentence.doc_id) & (Event.trigger_start == Sentence.char_start))
        .where(Event.entity_id == entity.id)
    ).all()
    seen: set[int] = set()
    evidence: list[tuple[int, str]] = []
    used = 0
    for sid, text in [*trigger_rows, *((r[0], r[1]) for r in rows)]:
        if sid in seen or len(text) < 25:
            continue
        if len(evidence) >= ENTITY_EVIDENCE_SENTENCES or used + len(text) > EVIDENCE_BUDGET_CHARS:
            break
        seen.add(sid)
        evidence.append((sid, text))
        used += len(text) + 8
    return evidence


def _store(
    session: Session,
    result: SummaryResult,
    *,
    scope: str,
    model: str,
    run_id: int | None,
    doc_id: int | None = None,
    entity_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Summary:
    summary = Summary(
        scope=scope,
        doc_id=doc_id,
        entity_id=entity_id,
        window_start=start,
        window_end=end,
        model=model,
        prompt_version=PROMPT_VERSION,
        run_id=run_id,
    )
    session.add(summary)
    session.flush()
    session.add_all(
        Claim(
            summary_id=summary.id,
            idx=i,
            text=c.text,
            verification="unverified",
            cited=c.sources,
            evidence_sentence_id=c.sources[0] if c.sources else None,
        )
        for i, c in enumerate(result.claims)
    )
    session.flush()
    return summary


def _count(stats: SummaryStats, result: SummaryResult) -> None:
    stats.summaries += 1
    stats.claims += len(result.claims)
    stats.prompt_tokens += result.prompt_tokens
    stats.completion_tokens += result.completion_tokens
    stats.seconds += result.seconds
    stats.dropped_sources += result.dropped_sources


def summarize_one(
    session: Session, llm: Llm, model: str, doc: Document, run_id: int | None = None
) -> Summary | None:
    """Summarise one document (replacing its earlier summary). None when there is too little evidence."""
    evidence = document_evidence(session, doc)
    if len(evidence) < 2:
        return None
    result = summarise(llm, model, subject=doc.title, scope="document", evidence=evidence)
    session.execute(delete(Summary).where(Summary.doc_id == doc.id, Summary.scope == "document"))
    return _store(session, result, scope="document", model=model, run_id=run_id, doc_id=doc.id)


def summarize_documents(
    session: Session, llm: Llm, model: str, *, limit: int | None = None, redo: bool = False
) -> SummaryStats:
    stmt = select(Document).where(Document.status.in_(("parsed", "analysed")))
    if not redo:
        stmt = stmt.where(
            ~select(Summary.id).where(Summary.doc_id == Document.id, Summary.scope == "document").exists()
        )
    stmt = stmt.order_by(desc(Document.published_at).nulls_last(), Document.id)
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = SummaryStats()
    if not docs:
        return stats
    with recorded_run(
        session,
        "summary",
        model=model,
        prompt_version=PROMPT_VERSION,
        params={"scope": "document", "n": len(docs)},
    ) as run:
        for doc in docs:
            evidence = document_evidence(session, doc)
            if len(evidence) < 2:
                continue
            try:
                result = summarise(llm, model, subject=doc.title, scope="document", evidence=evidence)
            except LlmError as exc:
                log.warning("summary failed for %s: %s", doc.title, exc)
                stats.failed += 1
                continue
            session.execute(delete(Summary).where(Summary.doc_id == doc.id, Summary.scope == "document"))
            _store(session, result, scope="document", model=model, run_id=run.id, doc_id=doc.id)
            _count(stats, result)
            session.commit()
    return stats


def summarize_entities(
    session: Session,
    llm: Llm,
    model: str,
    *,
    window: str = "365d",
    top: int = 25,
    min_sentences: int = 3,
) -> SummaryStats:
    """Summaries for the companies with the most mentions in the window."""
    anchor = anchor_date(session)
    start = window_start(anchor, window)
    stmt = (
        select(Entity)
        .join(Mention, Mention.entity_id == Entity.id)
        .join(Document, Document.id == Mention.doc_id)
        .where(Entity.kind.in_(("company", "bank")))
        .group_by(Entity.id)
        .order_by(desc(func.count(Mention.id)))
        .limit(top)
    )
    if start is not None:
        stmt = stmt.where(Document.published_at >= start)
    entities = list(session.scalars(stmt))
    stats = SummaryStats()
    if not entities:
        return stats
    with recorded_run(
        session,
        "summary",
        model=model,
        prompt_version=PROMPT_VERSION,
        params={"scope": "entity", "n": len(entities)},
    ) as run:
        for ent in entities:
            evidence = entity_evidence(session, ent, start, anchor)
            if len(evidence) < min_sentences:
                continue
            try:
                result = summarise(llm, model, subject=ent.canonical_name, scope="entity", evidence=evidence)
            except LlmError as exc:
                log.warning("summary failed for %s: %s", ent.canonical_name, exc)
                stats.failed += 1
                continue
            session.execute(
                delete(Summary).where(
                    Summary.entity_id == ent.id,
                    Summary.scope == "entity_window",
                    Summary.window_end == anchor,
                )
            )
            _store(
                session, result, scope="entity_window", model=model, run_id=run.id,
                entity_id=ent.id, start=start, end=anchor,
            )  # fmt: skip
            _count(stats, result)
            session.commit()
    return stats
