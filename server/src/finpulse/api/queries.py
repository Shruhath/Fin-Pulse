"""Read queries behind the API. Every number returned is computed from stored rows.

Windows are anchored on the newest document date in the corpus, not on today's date, so a
corpus that was collected a while ago still shows its latest period.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from math import sqrt

from sqlalchemy import Select, and_, desc, func, select
from sqlalchemy.orm import Session

from finpulse.db.models import (
    Claim,
    Document,
    Entity,
    EntityAlias,
    Event,
    Mention,
    MentionSentiment,
    Sentence,
    Summary,
)
from finpulse.db.views import entity_daily
from finpulse.events.headline import headline
from finpulse.events.taxonomy import EVENT_GROUP, EventType
from finpulse.preprocess.normalize import format_inr, mask_pan

from . import schemas as s

SCORE_BAND = 0.15  # |score| below this is shown as neutral
WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
MAX_ENTITIES = 200


def label_for(score: float | None) -> s.SentimentLabel | None:
    if score is None:
        return None
    return "positive" if score > SCORE_BAND else "negative" if score < -SCORE_BAND else "neutral"


def anchor_date(db: Session) -> date | None:
    return db.scalar(select(func.max(Document.published_at)))


def window_start(anchor: date | None, window: str) -> date | None:
    if anchor is None or window == "all":
        return None
    return anchor - timedelta(days=WINDOW_DAYS[window])


def active_model(db: Session) -> str | None:
    """The sentiment model whose predictions are shown: the one that scored most recently."""
    return db.scalar(select(MentionSentiment.model_version).order_by(desc(MentionSentiment.id)).limit(1))


# --------------------------------------------------------------------------- status


def corpus_status(db: Session) -> s.CorpusStatus:
    return s.CorpusStatus(
        documents=db.scalar(select(func.count()).select_from(Document)) or 0,
        entities=db.scalar(select(func.count(func.distinct(Mention.entity_id)))) or 0,
        events=db.scalar(select(func.count()).select_from(Event)) or 0,
        last_ingest_at=db.scalar(select(func.max(Document.retrieved_at))),
    )


# --------------------------------------------------------------------------- entities


def _daily_filter(model: str | None, start: date | None, end: date | None, lower_open: bool = False):
    conds = [entity_daily.c.model_version == model]
    if start is not None:
        conds.append(entity_daily.c.day > start if lower_open else entity_daily.c.day >= start)
    if end is not None:
        conds.append(entity_daily.c.day <= end)
    return and_(*conds)


def _aggregate(model: str | None, start: date | None, end: date | None, lower_open: bool = False) -> Select:
    n = func.sum(entity_daily.c.mentions)
    return (
        select(
            entity_daily.c.entity_id,
            n.label("n"),
            (func.sum(entity_daily.c.score_mean * entity_daily.c.mentions) / n).label("score"),
            (func.sum(entity_daily.c.confidence_mean * entity_daily.c.mentions) / n).label("conf"),
        )
        .where(_daily_filter(model, start, end, lower_open))
        .group_by(entity_daily.c.entity_id)
    )


def entity_rows(
    db: Session,
    window: str,
    *,
    q: str | None = None,
    slugs: Sequence[str] | None = None,
    sort: str = "mentions",
    limit: int = MAX_ENTITIES,
    with_series: bool = True,
) -> list[s.EntityRow]:
    anchor, model = anchor_date(db), active_model(db)
    if anchor is None or model is None:
        return []
    start = window_start(anchor, window)
    cur = _aggregate(model, start, anchor).subquery("cur")
    stmt = select(Entity, cur.c.n, cur.c.score, cur.c.conf).join(cur, cur.c.entity_id == Entity.id)
    stmt = stmt.where(Entity.kind.in_(("company", "bank")))
    if q:
        stmt = stmt.where(Entity.canonical_name.ilike(f"%{q}%") | Entity.nse_symbol.ilike(f"%{q}%"))
    if slugs is not None:
        stmt = stmt.where(Entity.slug.in_(slugs))
    order = {
        "score": desc(cur.c.score),
        "name": Entity.canonical_name,
        "mentions": desc(cur.c.n),
    }.get(sort, desc(cur.c.n))
    rows = db.execute(stmt.order_by(order, Entity.id).limit(limit)).all()
    if not rows:
        return []

    ids = [r[0].id for r in rows]
    previous: dict[int, float] = {}
    if start is not None:
        span = anchor - start
        prev = _aggregate(model, start - span, start, lower_open=True).where(
            entity_daily.c.entity_id.in_(ids)
        )
        previous = {r.entity_id: r.score for r in db.execute(prev)}

    series: dict[int, list[s.SeriesPoint]] = defaultdict(list)
    if with_series:
        daily = select(entity_daily.c.entity_id, entity_daily.c.day, entity_daily.c.score_mean).where(
            _daily_filter(model, start, anchor), entity_daily.c.entity_id.in_(ids)
        )
        for r in db.execute(daily.order_by(entity_daily.c.day)):
            series[r.entity_id].append(s.SeriesPoint(t=r.day, v=r.score_mean))

    out = []
    for ent, n, score, conf in rows:
        delta = (score - previous[ent.id]) if ent.id in previous and score is not None else None
        out.append(
            s.EntityRow(
                id=ent.slug,
                name=ent.canonical_name,
                ticker=ent.nse_symbol or "",
                sector=ent.sector or "",
                kind=ent.kind,
                score=score,
                delta=delta,
                sentiment=label_for(score),
                mentions=int(n),
                confidence=conf,
                series=series[ent.id],
            )
        )
    return out


# --------------------------------------------------------------------------- market aggregate


def market_series(db: Session, window: str) -> list[s.MarketPoint]:
    """Daily mean and spread of entity scores, pooled across entities by mention count."""
    anchor, model = anchor_date(db), active_model(db)
    if anchor is None or model is None:
        return []
    start = window_start(anchor, window)
    rows = db.execute(
        select(
            entity_daily.c.day, entity_daily.c.score_mean, entity_daily.c.score_std, entity_daily.c.mentions
        )
        .where(_daily_filter(model, start, anchor))
        .order_by(entity_daily.c.day)
    ).all()
    by_day: dict[date, list[tuple[float, float, int]]] = defaultdict(list)
    for r in rows:
        by_day[r.day].append((r.score_mean, r.score_std, r.mentions))
    out = []
    for day, items in sorted(by_day.items()):
        n = sum(m for _, _, m in items)
        mean = sum(mu * m for mu, _, m in items) / n
        var = sum(m * (sd * sd + mu * mu) for mu, sd, m in items) / n - mean * mean
        out.append(s.MarketPoint(t=day, mean=mean, std=sqrt(max(var, 0.0)), n=n))
    return out


# --------------------------------------------------------------------------- events


def _event_amount_args(ev: Event) -> dict[str, str]:
    args = {k: str(v) for k, v in (ev.arguments or {}).items()}
    if ev.amount_inr is not None:
        args = {"amount": format_inr(ev.amount_inr), **args}
    return args


def event_markers(
    db: Session,
    *,
    window: str | None = None,
    entity_slug: str | None = None,
    doc_id: int | None = None,
    event_type: str | None = None,
    limit: int = 500,
) -> list[tuple[Event, Document, Entity | None]]:
    stmt = (
        select(Event, Document, Entity)
        .join(Document, Document.id == Event.doc_id)
        .join(Entity, Entity.id == Event.entity_id, isouter=True)
    )
    if window:
        start = window_start(anchor_date(db), window)
        if start is not None:
            stmt = stmt.where(Event.event_date >= start)
    if entity_slug:
        stmt = stmt.where(Entity.slug == entity_slug)
    if doc_id is not None:
        stmt = stmt.where(Event.doc_id == doc_id)
    if event_type:
        stmt = stmt.where(Event.type == event_type)
    rows = db.execute(stmt.order_by(desc(Event.event_date).nulls_last(), desc(Event.id)).limit(limit)).all()
    return [(e, d, ent) for e, d, ent in rows]


def to_marker(ev: Event, doc: Document, ent: Entity | None) -> s.EventMarker:
    name = ent.canonical_name if ent else None
    return s.EventMarker(
        id=str(ev.id),
        t=ev.event_date,
        type=ev.type,
        group=EVENT_GROUP[EventType(ev.type)],
        entity_id=ent.slug if ent else None,
        entity_name=name,
        headline=headline(ev.type, name, ev.amount_inr, ev.arguments or {}),
        source=doc.source_kind,
        document_id=str(doc.id),
    )


def to_record(ev: Event, doc: Document, ent: Entity | None) -> s.EventRecord:
    marker = to_marker(ev, doc, ent)
    return s.EventRecord(
        **marker.model_dump(),
        sentiment=None,
        confidence=ev.confidence,
        trigger=(
            s.Span(start=ev.trigger_start, end=ev.trigger_end)
            if ev.trigger_start is not None and ev.trigger_end is not None
            else None
        ),
        arguments=_event_amount_args(ev),
        extractor=ev.extractor,
    )


# --------------------------------------------------------------------------- documents


def _doc_entities(db: Session, doc_ids: Iterable[int], model: str | None) -> dict[int, list[s.FilingEntity]]:
    ids = list(doc_ids)
    if not ids:
        return {}
    n = func.count(Mention.id)
    score = func.avg(MentionSentiment.p_pos - MentionSentiment.p_neg)
    rows = db.execute(
        select(Mention.doc_id, Entity.slug, Entity.canonical_name, n, score)
        .join(Entity, Entity.id == Mention.entity_id)
        .join(
            MentionSentiment,
            and_(MentionSentiment.mention_id == Mention.id, MentionSentiment.model_version == model),
            isouter=True,
        )
        .where(Mention.doc_id.in_(ids), Entity.kind.in_(("company", "bank")))
        .group_by(Mention.doc_id, Entity.slug, Entity.canonical_name)
        .order_by(Mention.doc_id, desc(n))
    ).all()
    out: dict[int, list[s.FilingEntity]] = defaultdict(list)
    for doc_id, slug, name, _, sc in rows:
        if len(out[doc_id]) < 4:
            out[doc_id].append(s.FilingEntity(id=slug, name=name, sentiment=label_for(sc)))
    return out


def filing_items(db: Session, docs: Sequence[Document]) -> list[s.FilingItem]:
    entities = _doc_entities(db, [d.id for d in docs], active_model(db))
    return [
        s.FilingItem(
            id=str(d.id),
            title=d.title,
            source=d.source_kind,
            published_at=d.published_at,
            entities=entities.get(d.id, []),
            status=d.status,
        )
        for d in docs
    ]


def list_documents(
    db: Session,
    *,
    source: str | None = None,
    status: str | None = None,
    q: str | None = None,
    window: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[s.FilingItem]:
    stmt = select(Document)
    if source:
        stmt = stmt.where(Document.source_kind == source)
    if status:
        stmt = stmt.where(Document.status == status)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    if window:
        start = window_start(anchor_date(db), window)
        if start is not None:
            stmt = stmt.where(Document.published_at >= start)
    stmt = (
        stmt.order_by(desc(Document.published_at).nulls_last(), desc(Document.id)).limit(limit).offset(offset)
    )
    return filing_items(db, list(db.scalars(stmt)))


def document_detail(db: Session, doc: Document) -> s.DocumentDetail:
    model = active_model(db)
    rows = db.execute(
        select(Mention, Entity, MentionSentiment)
        .join(Entity, Entity.id == Mention.entity_id, isouter=True)
        .join(
            MentionSentiment,
            and_(MentionSentiment.mention_id == Mention.id, MentionSentiment.model_version == model),
            isouter=True,
        )
        .where(Mention.doc_id == doc.id)
        .order_by(Mention.char_start)
    ).all()
    spans = [
        s.EntitySpan(
            start=m.char_start,
            end=m.char_end,
            entity_id=ent.slug if ent else None,
            surface=m.surface,
            sentiment=ms.label if ms else None,
            confidence=ms.confidence if ms else None,
        )
        for m, ent, ms in rows
    ]
    item = filing_items(db, [doc])[0]
    return s.DocumentDetail(
        **item.model_dump(),
        url=doc.url,
        words=doc.n_words,
        pages=doc.n_pages,
        ocr=doc.ocr_used,
        text=mask_pan(doc.clean_text),  # same length as the stored text, so offsets still line up
        spans=spans,
        events=[to_record(*row) for row in event_markers(db, doc_id=doc.id)],
        summary=latest_summary(db, doc_id=doc.id),
    )


# --------------------------------------------------------------------------- summaries


def latest_summary(
    db: Session, *, doc_id: int | None = None, entity_id: int | None = None
) -> s.Summary | None:
    stmt = select(Summary).order_by(desc(Summary.generated_at), desc(Summary.id)).limit(1)
    stmt = (
        stmt.where(Summary.doc_id == doc_id)
        if doc_id is not None
        else stmt.where(Summary.entity_id == entity_id)
    )
    summary = db.scalar(stmt)
    if summary is None:
        return None
    claims = []
    for c in db.scalars(select(Claim).where(Claim.summary_id == summary.id).order_by(Claim.idx)):
        evidence = None
        if c.evidence_sentence_id is not None:
            row = db.execute(
                select(Sentence, Document)
                .join(Document, Document.id == Sentence.doc_id)
                .where(Sentence.id == c.evidence_sentence_id)
            ).first()
            if row:
                sent, d = row
                evidence = s.Evidence(
                    document_id=str(d.id),
                    document_title=d.title,
                    source=d.source_kind,
                    text=sent.text,
                    start=sent.char_start,
                    end=sent.char_end,
                )
        claims.append(
            s.Claim(
                id=str(c.id),
                text=c.text,
                verification=c.verification,
                entail=c.nli_entail,
                contradict=c.nli_contra,
                evidence=evidence,
            )
        )
    return s.Summary(
        id=str(summary.id),
        scope="document" if summary.scope == "document" else "entity",
        model=summary.model,
        generated_at=summary.generated_at,
        claims=claims,
    )


# --------------------------------------------------------------------------- company page


def company_detail(db: Session, slug: str, window: str) -> s.CompanyDetail | None:
    ent = db.scalar(select(Entity).where(Entity.slug == slug))
    if ent is None:
        return None
    model = active_model(db)
    rows = entity_rows(db, window, slugs=[slug], limit=1)
    # an entity with mentions but no scores in this window still has a page
    row = (
        rows[0]
        if rows
        else s.EntityRow(
            id=ent.slug,
            name=ent.canonical_name,
            ticker=ent.nse_symbol or "",
            sector=ent.sector or "",
            kind=ent.kind,
            score=None,
            delta=None,
            sentiment=None,
            mentions=db.scalar(select(func.count()).select_from(Mention).where(Mention.entity_id == ent.id))
            or 0,
            confidence=None,
            series=[],
        )
    )
    mention_rows = db.execute(
        select(Mention, Document, Sentence, MentionSentiment)
        .join(Document, Document.id == Mention.doc_id)
        .join(Sentence, Sentence.id == Mention.sentence_id, isouter=True)
        .join(
            MentionSentiment,
            and_(MentionSentiment.mention_id == Mention.id, MentionSentiment.model_version == model),
            isouter=True,
        )
        .where(Mention.entity_id == ent.id)
        .order_by(desc(Document.published_at).nulls_last(), Mention.char_start)
        .limit(40)
    ).all()
    mentions = []
    for m, d, sent, ms in mention_rows:
        if sent is None:
            continue
        mentions.append(
            s.Mention(
                document_id=str(d.id),
                document_title=d.title,
                source=d.source_kind,
                published_at=d.published_at,
                sentence=sent.text,
                start=m.char_start - sent.char_start,
                end=m.char_end - sent.char_start,
                sentiment=ms.label if ms else None,
                confidence=ms.confidence if ms else None,
            )
        )
    aliases = sorted(
        {a for a in db.scalars(select(EntityAlias.alias).where(EntityAlias.entity_id == ent.id))}
    )
    return s.CompanyDetail(
        entity=row,
        aliases=aliases,
        events=[to_record(*r) for r in event_markers(db, entity_slug=slug)],
        mentions=mentions,
        summary=latest_summary(db, entity_id=ent.id),
    )
