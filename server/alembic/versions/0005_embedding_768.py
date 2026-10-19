"""sentence embeddings are 768-dimensional (BAAI/bge-base-en-v1.5)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19

The column held no vectors yet, so nothing is lost; any that exist are cleared because a vector
from another model would be meaningless against the new ones.
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sentences_embedding_hnsw")
    op.execute("UPDATE sentences SET embedding = NULL")
    op.execute("ALTER TABLE sentences ALTER COLUMN embedding TYPE vector(768)")
    op.execute(
        "CREATE INDEX ix_sentences_embedding_hnsw ON sentences USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sentences_embedding_hnsw")
    op.execute("UPDATE sentences SET embedding = NULL")
    op.execute("ALTER TABLE sentences ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        "CREATE INDEX ix_sentences_embedding_hnsw ON sentences USING hnsw (embedding vector_cosine_ops)"
    )
