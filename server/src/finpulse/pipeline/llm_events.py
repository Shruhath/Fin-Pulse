"""LLM event stage: Qwen reads the pruned document and returns typed events."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from finpulse.core.offsets import Span
from finpulse.db.models import Document, Entity, Event, Mention, Sentence
from finpulse.entities.resolver import Resolver
from finpulse.events.llm import PROMPT_VERSION, ExtractionResult, extract_llm_events
from finpulse.llm.client import Llm, LlmError
from finpulse.summarize.prune import select as select_sentences

from .runs import recorded_run

log = logging.getLogger(__name__)

EXTRACTOR = "llm"
PROMPT_BUDGET_CHARS = 14_000  # about 3.5k tokens of sentences inside an 8k context with the taxonomy


@dataclass(slots=True)
class DocOutcome:
    stored: int
    invalid: int
    result: ExtractionResult


@dataclass(slots=True)
class LlmEventStats:
    documents: int = 0
    events: int = 0
    invalid: int = 0
    failed: int = 0
    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    dropped: Counter[str] = field(default_factory=Counter)


def document_entities(session: Session, doc_id: int, limit: int = 6) -> list[str]:
    """Names of the entities the document is about: title parties first, then the most mentioned."""
    rows = session.execute(
        select(Entity.canonical_name, func.count(Mention.id), func.min(Mention.char_start))
        .join(Mention, Mention.entity_id == Entity.id)
        .where(Mention.doc_id == doc_id)
        .group_by(Entity.id)
        .order_by(func.count(Mention.id).desc())
        .limit(limit)
    ).all()
    return [name for name, _, _ in rows]


def prune_document(session: Session, doc: Document, sentences: list[Sentence]) -> list[int]:
    """Pick the sentences to show, keeping every rule-detected operative sentence, and record the choice."""
    rule_triggers = [
        Span(e.trigger_start, e.trigger_end)
        for e in session.scalars(select(Event).where(Event.doc_id == doc.id, Event.extractor == "rules"))
        if e.trigger_start is not None and e.trigger_end is not None
    ]
    must = [
        i
        for i, s in enumerate(sentences)
        if any(Span(s.char_start, s.char_end).overlaps(t) for t in rule_triggers)
    ]
    chosen = set(
        select_sentences([s.text for s in sentences], budget_chars=PROMPT_BUDGET_CHARS, must_keep=must)
    )
    for i, s in enumerate(sentences):
        s.kept_after_prune = i in chosen
    return sorted(chosen)


def extract_for_document(
    session: Session, llm: Llm, model: str, doc: Document, resolver: Resolver, run_id: int | None
) -> DocOutcome:
    """Replace the document's LLM events."""
    sentences = list(
        session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
    )
    chosen = prune_document(session, doc, sentences)
    shown = [(sentences[i].idx, sentences[i].text) for i in chosen]
    by_idx = {s.idx: s for s in sentences}
    result = extract_llm_events(
        llm,
        model,
        title=doc.title,
        source=doc.source_kind,
        doc_type=doc.doc_type,
        entities=document_entities(session, doc.id),
        shown=shown,
    )
    session.execute(delete(Event).where(Event.doc_id == doc.id, Event.extractor == EXTRACTOR))
    invalid = 0
    for d in result.drafts:
        sentence = by_idx[d.trigger_sentence]
        entity_id = None
        if d.entity_name:
            res = resolver.resolve(d.entity_name)
            entity_id = res.entity_id
        session.add(
            Event(
                doc_id=doc.id,
                entity_id=entity_id,
                type=d.type.value,
                trigger_start=sentence.char_start,
                trigger_end=sentence.char_end,
                arguments=d.arguments,
                event_date=doc.published_at,
                amount_inr=d.amount_inr,
                confidence=None,
                schema_valid=d.schema_valid,
                extractor=EXTRACTOR,
                run_id=run_id,
            )
        )
        invalid += not d.schema_valid
    session.flush()
    return DocOutcome(len(result.drafts), invalid, result)


def llm_extract_pending(
    session: Session,
    llm: Llm,
    model: str,
    *,
    limit: int | None = None,
    redo: bool = False,
    source_kinds: tuple[str, ...] = ("SEBI", "NCLT"),
) -> LlmEventStats:
    stmt = select(Document).where(
        Document.status.in_(("parsed", "analysed")), Document.source_kind.in_(source_kinds)
    )
    if not redo:
        stmt = stmt.where(
            ~select(Event.id).where(Event.doc_id == Document.id, Event.extractor == EXTRACTOR).exists()
        )
    stmt = stmt.order_by(Document.id)
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = LlmEventStats()
    if not docs:
        return stats
    resolver = Resolver.from_session(session)
    with recorded_run(
        session,
        "events-llm",
        model=model,
        prompt_version=PROMPT_VERSION,
        params={"documents": len(docs), "budget_chars": PROMPT_BUDGET_CHARS},
    ) as run:
        for doc in docs:
            try:
                outcome = extract_for_document(session, llm, model, doc, resolver, run.id)
            except LlmError as exc:  # unusable answers for one document must not stop the batch
                log.warning("LLM event extraction failed for %s: %s", doc.title, exc)
                stats.failed += 1
                session.rollback()
                continue
            result = outcome.result
            stats.documents += 1
            stats.events += outcome.stored
            stats.invalid += outcome.invalid
            stats.attempts += result.attempts
            stats.prompt_tokens += result.prompt_tokens
            stats.completion_tokens += result.completion_tokens
            stats.seconds += result.seconds
            stats.dropped.update(result.dropped)
            session.commit()
    return stats


def extract_llm_one(session: Session, llm: Llm, model: str, doc: Document) -> DocOutcome:
    """The LLM events of a single document, with a run record (the live analysis path)."""
    resolver = Resolver.from_session(session)
    with recorded_run(
        session, "events-llm", model=model, prompt_version=PROMPT_VERSION, params={"documents": 1}
    ) as run:
        outcome = extract_for_document(session, llm, model, doc, resolver, run.id)
        session.commit()
    return outcome
