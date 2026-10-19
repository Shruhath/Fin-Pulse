"""claims.cited and the agreements table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column(
            "cited",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "agreements",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("task", sa.String(length=24), nullable=False),
        sa.Column("measure", sa.String(length=24), nullable=False),
        sa.Column("annotators", sa.String(length=96), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreements")),
        sa.UniqueConstraint(
            "task", "measure", "annotators", name=op.f("uq_agreements_task_measure_annotators")
        ),
    )


def downgrade() -> None:
    op.drop_table("agreements")
    op.drop_column("claims", "cited")
