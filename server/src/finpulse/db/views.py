"""Core handles for database views (the ORM models cover tables only)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Date, Float, Integer, String, Table

from .base import Base

# One row per entity, day and sentiment model version; refreshed after scoring.
entity_daily = Table(
    "entity_daily",
    Base.metadata,
    Column("entity_id", BigInteger),
    Column("day", Date),
    Column("model_version", String),
    Column("score_mean", Float),
    Column("score_std", Float),
    Column("mentions", Integer),
    Column("confidence_mean", Float),
    info={"is_view": True},
)
