"""documents submitted for live analysis are kept out of the corpus aggregates

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20

A pasted text, an upload or a fetched URL is stored so its analysis can be read back by id, but it is
not a collected disclosure: it must not move a company's sentiment, add an event to the timeline or
shift the window the overview is anchored on. `entity_daily` is rebuilt without such documents.
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_VIEW = """
    CREATE MATERIALIZED VIEW entity_daily AS
    SELECT m.entity_id,
           d.published_at AS day,
           ms.model_version,
           avg(ms.p_pos - ms.p_neg)::float8 AS score_mean,
           coalesce(stddev_pop(ms.p_pos - ms.p_neg), 0)::float8 AS score_std,
           count(*) AS mentions,
           avg(ms.confidence)::float8 AS confidence_mean
    FROM mention_sentiment ms
    JOIN mentions m ON m.id = ms.mention_id
    JOIN documents d ON d.id = m.doc_id
    WHERE m.entity_id IS NOT NULL AND d.published_at IS NOT NULL{extra}
    GROUP BY m.entity_id, d.published_at, ms.model_version
"""


def _rebuild(extra: str) -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS entity_daily")
    op.execute(_VIEW.format(extra=extra))
    op.execute("CREATE UNIQUE INDEX uq_entity_daily ON entity_daily (entity_id, day, model_version)")


def upgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN is_submission boolean NOT NULL DEFAULT false")
    op.execute("UPDATE documents SET is_submission = true WHERE meta->>'origin' LIKE 'analyze-%'")
    _rebuild("\n      AND NOT d.is_submission")


def downgrade() -> None:
    _rebuild("")
    op.execute("ALTER TABLE documents DROP COLUMN is_submission")
