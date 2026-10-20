"""Database schema (docs/PLAN.md section 4).

Offsets in `mentions`, `events` and `sentences` are half-open character ranges into
`documents.clean_text`. Gold and silver annotations never share a row type, and
contradicted summary claims are kept, not dropped.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

EMBEDDING_DIM = 768  # BAAI/bge-base-en-v1.5

SOURCE_KINDS = ("BSE", "NSE", "SEBI", "RBI", "NCLT", "NEWS")
DOC_STATUSES = ("ingested", "parsed", "analysed", "failed")


def _now() -> Any:
    return func.now()


class Source(Base):
    __tablename__ = "sources"

    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    base_url: Mapped[str | None] = mapped_column(Text)
    robots_ok: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"source_kind IN {SOURCE_KINDS!r}", name="source_kind"),
        CheckConstraint(f"status IN {DOC_STATUSES!r}", name="status"),
        Index("ix_documents_published_at", "published_at"),
        Index("ix_documents_source_kind_published_at", "source_kind", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_kind: Mapped[str] = mapped_column(ForeignKey("sources.kind"), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    raw_path: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    n_words: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    n_pages: Mapped[int | None] = mapped_column(Integer)
    lang: Mapped[str] = mapped_column(String(8), nullable=False, server_default="en")
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ingested")
    minhash_cluster: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )

    sentences: Mapped[list[Sentence]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Sentence(Base):
    __tablename__ = "sentences"
    __table_args__ = (
        UniqueConstraint("doc_id", "idx"),
        Index("ix_sentences_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_sentences_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    kept_after_prune: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))

    document: Mapped[Document] = relationship(back_populates="sentences")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint("kind IN ('company', 'regulator', 'bank', 'person')", name="kind"),
        Index("ix_entities_nse_symbol", "nse_symbol"),
        Index("ix_entities_isin", "isin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    bse_code: Mapped[str | None] = mapped_column(String(16))
    nse_symbol: Mapped[str | None] = mapped_column(String(32))
    isin: Mapped[str | None] = mapped_column(String(12))
    cin: Mapped[str | None] = mapped_column(String(21))
    sector: Mapped[str | None] = mapped_column(String(96))
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="company")

    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan")


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "alias_norm"),
        Index("ix_entity_aliases_alias_norm", "alias_norm"),
        Index(
            "ix_entity_aliases_alias_norm_trgm",
            "alias_norm",
            postgresql_using="gin",
            postgresql_ops={"alias_norm": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_norm: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)  # nse | bse | sentfin | corpus | manual

    entity: Mapped[Entity] = relationship(back_populates="aliases")


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        CheckConstraint("char_end > char_start", name="span"),
        Index("ix_mentions_doc_id", "doc_id"),
        Index("ix_mentions_entity_id", "entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    sentence_id: Mapped[int | None] = mapped_column(ForeignKey("sentences.id", ondelete="SET NULL"))
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(Text, nullable=False)
    ner_model: Mapped[str] = mapped_column(String(64), nullable=False)
    ner_score: Mapped[float | None] = mapped_column(Float)
    link_method: Mapped[str | None] = mapped_column(String(24))  # exact | normalised | fuzzy | unresolved
    link_score: Mapped[float | None] = mapped_column(Float)

    sentiments: Mapped[list[MentionSentiment]] = relationship(
        back_populates="mention", cascade="all, delete-orphan"
    )


class MentionSentiment(Base):
    __tablename__ = "mention_sentiment"
    __table_args__ = (
        UniqueConstraint("mention_id", "model_version"),
        CheckConstraint("label IN ('positive', 'negative', 'neutral')", name="label"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mention_id: Mapped[int] = mapped_column(ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(96), nullable=False)
    label: Mapped[str] = mapped_column(String(8), nullable=False)
    p_pos: Mapped[float] = mapped_column(Float, nullable=False)
    p_neg: Mapped[float] = mapped_column(Float, nullable=False)
    p_neu: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # calibrated

    mention: Mapped[Mention] = relationship(back_populates="sentiments")


class Run(Base):
    """One execution of a pipeline stage: the recorded evidence behind every stored prediction."""

    __tablename__ = "runs"
    __table_args__ = (CheckConstraint("status IN ('running', 'done', 'failed')", name="status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    model: Mapped[str | None] = mapped_column(String(96))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="running")
    error: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("extractor IN ('llm', 'rules')", name="extractor"),
        Index("ix_events_doc_id", "doc_id"),
        Index("ix_events_entity_id", "entity_id"),
        Index("ix_events_event_date", "event_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_start: Mapped[int | None] = mapped_column(Integer)
    trigger_end: Mapped[int | None] = mapped_column(Integer)
    arguments: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    event_date: Mapped[date | None] = mapped_column(Date)
    amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    confidence: Mapped[float | None] = mapped_column(Float)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    extractor: Mapped[str] = mapped_column(String(8), nullable=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))


class Summary(Base):
    __tablename__ = "summaries"
    __table_args__ = (CheckConstraint("scope IN ('document', 'entity_window')", name="scope"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    model: Mapped[str] = mapped_column(String(96), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())

    claims: Mapped[list[Claim]] = relationship(
        back_populates="summary", cascade="all, delete-orphan", order_by="Claim.idx"
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("summary_id", "idx"),
        CheckConstraint("verification IN ('entailed', 'contradicted', 'unverified')", name="verification"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    summary_id: Mapped[int] = mapped_column(ForeignKey("summaries.id", ondelete="CASCADE"), nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    verification: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    nli_entail: Mapped[float | None] = mapped_column(Float)
    nli_contra: Mapped[float | None] = mapped_column(Float)
    evidence_sentence_id: Mapped[int | None] = mapped_column(ForeignKey("sentences.id", ondelete="SET NULL"))
    retrieval_rank: Mapped[int | None] = mapped_column(Integer)
    cited: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))

    summary: Mapped[Summary] = relationship(back_populates="claims")


class IngestFailure(Base):
    """Dead letter for fetches that never yielded content."""

    __tablename__ = "ingest_failures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str | None] = mapped_column(String(8))
    failure_class: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class Job(Base):
    """Postgres-backed queue: the single GPU worker claims rows with FOR UPDATE SKIP LOCKED."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    stages: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint("label_source IN ('gold', 'silver')", name="label_source"),
        CheckConstraint("task IN ('ner', 'sentiment', 'event', 'summary')", name="task"),
        Index("ix_annotations_task_label_source", "task", "label_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(String(12), nullable=False)
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    label_source: Mapped[str] = mapped_column(String(8), nullable=False)
    annotator: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (CheckConstraint("stage IN ('ner', 'sentiment', 'events', 'summaries')", name="stage"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stage: Mapped[str] = mapped_column(String(12), nullable=False)
    model: Mapped[str] = mapped_column(String(96), nullable=False)
    baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    dataset: Mapped[str] = mapped_column(String(96), nullable=False)
    split: Mapped[str] = mapped_column(String(16), nullable=False)
    indian: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # confusion matrix, reliability bins
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    git_sha: Mapped[str | None] = mapped_column(String(40))
    data_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class Agreement(Base):
    """Inter-annotator agreement on the calibration set, one row per task and measure."""

    __tablename__ = "agreements"
    __table_args__ = (UniqueConstraint("task", "measure", "annotators"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(String(24), nullable=False)
    measure: Mapped[str] = mapped_column(String(24), nullable=False)  # cohen_kappa | fleiss_kappa | span_f1
    annotators: Mapped[str] = mapped_column(String(96), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    items: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class GoldPassage(Base):
    """A frozen passage that annotators label. Its text never changes once selected: the hash proves it."""

    __tablename__ = "gold_passages"
    __table_args__ = (
        UniqueConstraint("doc_id", "char_start", "char_end"),
        CheckConstraint("char_end > char_start", name="span"),
        CheckConstraint("role IN ('calibration', 'gold', 'dev')", name="role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stratum: Mapped[str] = mapped_column(String(64), nullable=False)
    has_rule_event: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    role: Mapped[str] = mapped_column(String(12), nullable=False, server_default="gold")
    ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    ocr_engine: Mapped[str | None] = mapped_column(String(64))
    ocr_dpi: Mapped[int | None] = mapped_column(Integer)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
