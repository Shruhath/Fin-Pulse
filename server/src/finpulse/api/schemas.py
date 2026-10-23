"""Response models: the contract with `web/`.

Field names are camelCase on the wire (`alias_generator`) and snake_case in Python. A value the
pipeline has not produced is `None`, never a placeholder: a corpus without sentiment scores
returns null scores, and an empty corpus returns empty lists.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

SentimentLabel = Literal["positive", "negative", "neutral"]
Verification = Literal["entailed", "contradicted", "unverified"]
SourceKind = Literal["BSE", "NSE", "SEBI", "RBI", "NCLT", "NEWS"]
Window = Literal["7d", "30d", "90d", "365d", "all"]
StageKey = Literal["ingest", "parse", "entities", "sentiment", "events", "summary", "verify"]


class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class CorpusStatus(Api):
    documents: int
    entities: int
    events: int
    last_ingest_at: datetime | None


class SourceCount(Api):
    kind: SourceKind
    documents: int


class MarketPoint(Api):
    t: date
    mean: float
    std: float
    n: int


class SeriesPoint(Api):
    t: date
    v: float


class EntityRow(Api):
    id: str
    name: str
    ticker: str
    sector: str
    kind: str
    score: float | None
    delta: float | None
    sentiment: SentimentLabel | None
    mentions: int
    confidence: float | None
    series: list[SeriesPoint]


class EventMarker(Api):
    id: str
    t: date | None
    type: str
    group: str
    entity_id: str | None
    entity_name: str | None
    headline: str
    source: SourceKind
    document_id: str


class FilingEntity(Api):
    id: str
    name: str
    sentiment: SentimentLabel | None


class FilingItem(Api):
    id: str
    title: str
    source: SourceKind
    published_at: date | None
    entities: list[FilingEntity]
    status: Literal["ingested", "parsed", "analysed", "failed"]


class Overview(Api):
    window: Window
    as_of: date | None
    corpus: CorpusStatus
    sources: list[SourceCount]
    market: list[MarketPoint]
    events: list[EventMarker]
    entities: list[EntityRow]
    filings: list[FilingItem]
    sentiment_model: str | None


class Span(Api):
    start: int
    end: int


class EntitySpan(Api):
    start: int
    end: int
    entity_id: str | None
    surface: str
    sentiment: SentimentLabel | None
    confidence: float | None


class EventRecord(EventMarker):
    sentiment: SentimentLabel | None
    confidence: float | None
    trigger: Span | None
    arguments: dict[str, str]
    extractor: Literal["llm", "rules"]


class Evidence(Api):
    document_id: str
    document_title: str
    source: SourceKind
    text: str
    start: int | None = None
    end: int | None = None


class Claim(Api):
    id: str
    text: str
    verification: Verification
    entail: float | None
    contradict: float | None
    evidence: Evidence | None


class Summary(Api):
    id: str
    scope: Literal["document", "entity"]
    model: str
    generated_at: datetime
    claims: list[Claim]


class DocumentDetail(FilingItem):
    url: str | None
    words: int
    pages: int | None
    ocr: bool
    text: str
    spans: list[EntitySpan]
    events: list[EventRecord]
    summary: Summary | None


class Mention(Api):
    document_id: str
    document_title: str
    source: SourceKind
    published_at: date | None
    sentence: str
    start: int
    end: int
    sentiment: SentimentLabel | None
    confidence: float | None


class CompanyDetail(Api):
    entity: EntityRow
    aliases: list[str]
    events: list[EventRecord]
    mentions: list[Mention]
    summary: Summary | None


class MetricRow(Api):
    task: Literal["ner", "sentiment", "events", "summaries"]
    model: str
    baseline: bool
    dataset: str
    indian: bool
    metrics: dict[str, float]
    git_sha: str | None = None
    created_at: datetime | None = None


class Confusion(Api):
    model: str
    dataset: str
    labels: list[SentimentLabel]
    matrix: list[list[int]]


class ReliabilityBin(Api):
    confidence: float
    accuracy: float
    n: int


class Reliability(Api):
    model: str
    dataset: str
    before: list[ReliabilityBin]
    after: list[ReliabilityBin] | None
    ece_before: float
    ece_after: float | None


class Agreement(Api):
    task: str
    kappa: float
    items: int


class EvalReport(Api):
    generated_at: datetime | None
    rows: list[MetricRow]
    confusion: Confusion | None
    reliability: Reliability | None
    agreement: list[Agreement]


class JobStage(Api):
    key: StageKey
    status: Literal["pending", "running", "done", "failed", "skipped"]
    ms: int | None
    note: str | None


class Job(Api):
    id: str
    status: Literal["queued", "running", "done", "failed"]
    stages: list[JobStage]
    document_id: str | None
    error: str | None = None


class AnalyzeRequest(Api):
    text: str | None = None
    url: str | None = None
    title: str | None = None
    source: SourceKind = "NEWS"


class AnalyzeAccepted(Api):
    job_id: str


class SearchCompany(Api):
    id: str
    name: str
    ticker: str


class SearchFiling(Api):
    id: str
    title: str
    source: SourceKind


class SearchIndex(Api):
    companies: list[SearchCompany]
    filings: list[SearchFiling]


class Health(Api):
    status: Literal["ok", "degraded"]
    database: bool
    ollama: bool
    gpu: str | None
    tesseract: str | None
    sentiment_model: str | None
    queued_jobs: int


class PipelineConfig(Api):
    sentiment_model: str | None
    event_model: str
    summary_model: str
    score_band: float
    ocr_dpi: int
    ocr_min_words_per_page: int
