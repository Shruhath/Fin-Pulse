"""gold_passages: the frozen passages that annotators label

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_passages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("doc_id", sa.BigInteger(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("stratum", sa.String(length=64), nullable=False),
        sa.Column("has_rule_event", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("role", sa.String(length=12), server_default="gold", nullable=False),
        sa.Column("ocr", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ocr_engine", sa.String(length=64), nullable=True),
        sa.Column("ocr_dpi", sa.Integer(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_end > char_start", name=op.f("ck_gold_passages_span")),
        sa.CheckConstraint("role IN ('calibration', 'gold', 'dev')", name=op.f("ck_gold_passages_role")),
        sa.ForeignKeyConstraint(
            ["doc_id"], ["documents.id"], name=op.f("fk_gold_passages_doc_id_documents"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gold_passages")),
        sa.UniqueConstraint(
            "doc_id", "char_start", "char_end", name=op.f("uq_gold_passages_doc_id_char_start_char_end")
        ),
    )


def downgrade() -> None:
    op.drop_table("gold_passages")
