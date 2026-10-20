"""Read endpoints for the corpus: overview, companies, documents, events, search, wallpaper."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from finpulse.api import queries as q
from finpulse.api import schemas as s
from finpulse.api.deps import get_db
from finpulse.db.models import Document, Entity, Mention
from finpulse.db.views import entity_daily

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
WindowParam = Annotated[s.Window, Query()]


@router.get("/status", response_model=s.CorpusStatus)
def status(db: Db) -> s.CorpusStatus:
    return q.corpus_status(db)


@router.get("/overview", response_model=s.Overview)
def overview(db: Db, window: WindowParam = "30d") -> s.Overview:
    source_rows = db.execute(
        select(Document.source_kind, func.count())
        .where(q.IN_CORPUS)
        .group_by(Document.source_kind)
        .order_by(desc(func.count()))
    ).all()
    start = q.window_start(q.anchor_date(db), window)
    docs_stmt = (
        select(Document)
        .where(q.IN_CORPUS)
        .order_by(desc(Document.published_at).nulls_last(), desc(Document.id))
        .limit(30)
    )
    if start is not None:
        docs_stmt = docs_stmt.where(Document.published_at >= start)
    return s.Overview(
        window=window,
        as_of=q.anchor_date(db),
        corpus=q.corpus_status(db),
        sources=[s.SourceCount(kind=k, documents=n) for k, n in source_rows],
        market=q.market_series(db, window),
        events=[q.to_marker(*row) for row in q.event_markers(db, window=window, limit=200)],
        entities=q.entity_rows(db, window, limit=40),
        filings=q.filing_items(db, list(db.scalars(docs_stmt))),
        sentiment_model=q.active_model(db),
    )


@router.get("/entities", response_model=list[s.EntityRow])
def entities(
    db: Db,
    window: WindowParam = "30d",
    sort: Annotated[str, Query(pattern="^(mentions|score|name)$")] = "mentions",
    q_: Annotated[str | None, Query(alias="q")] = None,
    limit: Annotated[int, Query(ge=1, le=q.MAX_ENTITIES)] = q.MAX_ENTITIES,
) -> list[s.EntityRow]:
    return q.entity_rows(db, window, q=q_, sort=sort, limit=limit)


@router.get("/entities/{slug}", response_model=s.CompanyDetail)
def entity(slug: str, db: Db, window: WindowParam = "30d") -> s.CompanyDetail:
    detail = q.company_detail(db, slug, window)
    if detail is None:
        raise HTTPException(404, "no such company")
    return detail


@router.get("/documents", response_model=list[s.FilingItem])
def documents(
    db: Db,
    source: Annotated[s.SourceKind | None, Query()] = None,
    status: Annotated[str | None, Query(pattern="^(ingested|parsed|analysed|failed)$")] = None,
    q_: Annotated[str | None, Query(alias="q")] = None,
    window: Annotated[s.Window | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[s.FilingItem]:
    return q.list_documents(
        db, source=source, status=status, q=q_, window=window, limit=page_size, offset=(page - 1) * page_size
    )


@router.get("/documents/{doc_id}", response_model=s.DocumentDetail)
def document(doc_id: int, db: Db) -> s.DocumentDetail:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "no such document")
    return q.document_detail(db, doc)


@router.get("/events", response_model=list[s.EventRecord])
def events(
    db: Db,
    window: Annotated[s.Window | None, Query()] = None,
    type_: Annotated[str | None, Query(alias="type")] = None,
    entity: Annotated[str | None, Query()] = None,
    extractor: Annotated[str, Query(pattern="^(best|llm|rules)$")] = "best",
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> list[s.EventRecord]:
    rows = q.event_markers(
        db, window=window, entity_slug=entity, event_type=type_, extractor=extractor, limit=limit
    )
    return q.event_records(db, rows)


@router.get("/summaries", response_model=list[s.Summary])
def summaries(
    db: Db,
    entity: Annotated[str | None, Query()] = None,
    window: Annotated[s.Window | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[s.Summary]:
    return q.list_summaries(db, entity_slug=entity, window=window, limit=limit)


@router.get("/search", response_model=s.SearchResults)
def search_corpus(
    db: Db, q_: Annotated[str, Query(alias="q", min_length=2, max_length=200)]
) -> s.SearchResults:
    return q.search(db, q_)


@router.get("/search/index", response_model=s.SearchIndex)
def search_index(db: Db) -> s.SearchIndex:
    mentions = func.count(Mention.id)
    company_rows = db.execute(
        select(Entity.slug, Entity.canonical_name, Entity.nse_symbol)
        .join(Mention, Mention.entity_id == Entity.id)
        .join(Document, Document.id == Mention.doc_id)
        .where(Entity.kind.in_(("company", "bank")), q.IN_CORPUS)
        .group_by(Entity.id)
        .order_by(desc(mentions))
        .limit(800)
    ).all()
    docs = db.execute(
        select(Document.id, Document.title, Document.source_kind)
        .where(q.IN_CORPUS)
        .order_by(desc(Document.published_at).nulls_last(), desc(Document.id))
        .limit(500)
    ).all()
    return s.SearchIndex(
        companies=[s.SearchCompany(id=slug, name=name, ticker=sym or "") for slug, name, sym in company_rows],
        filings=[s.SearchFiling(id=str(i), title=t, source=k) for i, t, k in docs],
    )


@router.get("/wallpaper", response_model=list[list[float]])
def wallpaper(db: Db) -> list[list[float]]:
    """Daily mean sentiment of the busiest companies over the last 90 days of the corpus, one row each.

    The grid is decoration for the desktop background. A day on which a company has no scored mention
    is drawn as 0 (no signal), so the field stays continuous; nothing else uses these values.
    """
    anchor, model = q.anchor_date(db), q.active_model(db)
    if anchor is None or model is None:
        return []
    start = anchor - timedelta(days=89)
    top = db.execute(
        select(entity_daily.c.entity_id)
        .where(
            entity_daily.c.model_version == model, entity_daily.c.day >= start, entity_daily.c.day <= anchor
        )
        .group_by(entity_daily.c.entity_id)
        .order_by(desc(func.sum(entity_daily.c.mentions)))
        .limit(60)
    ).scalars()
    ids = list(top)
    if not ids:
        return []
    by_entity: dict[int, dict[int, float]] = defaultdict(dict)
    for r in db.execute(
        select(entity_daily.c.entity_id, entity_daily.c.day, entity_daily.c.score_mean).where(
            entity_daily.c.model_version == model,
            entity_daily.c.entity_id.in_(ids),
            entity_daily.c.day >= start,
            entity_daily.c.day <= anchor,
        )
    ):
        by_entity[r.entity_id][(r.day - start).days] = r.score_mean
    grid = [[by_entity[i].get(d, 0.0) for d in range(90)] for i in ids]
    return sorted(grid, key=lambda row: row[-1])
