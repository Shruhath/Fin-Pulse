"""evaluation results can be recorded for question answering

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE eval_results DROP CONSTRAINT ck_eval_results_stage")
    op.execute(
        "ALTER TABLE eval_results ADD CONSTRAINT ck_eval_results_stage "
        "CHECK (stage IN ('ner', 'sentiment', 'events', 'summaries', 'qa'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM eval_results WHERE stage = 'qa'")
    op.execute("ALTER TABLE eval_results DROP CONSTRAINT ck_eval_results_stage")
    op.execute(
        "ALTER TABLE eval_results ADD CONSTRAINT ck_eval_results_stage "
        "CHECK (stage IN ('ner', 'sentiment', 'events', 'summaries'))"
    )
