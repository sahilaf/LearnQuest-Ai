"""M1: teachback_sessions - the Teach-Back (protege effect) loop.

One row per round of "teach Nova out of your own misconception". The question
and its correct answer are snapshotted into the row so a grade stays
reproducible even if the question is later edited or deleted.

Revision ID: 0007_m1_teachback_sessions
Revises: 0006_m2_learning_management
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_m1_teachback_sessions"
down_revision: Union[str, None] = "0006_m2_learning_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    op.create_table(
        "teachback_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("topic_tag", sa.String(length=100), nullable=False),
        sa.Column("misconception", sa.Text(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("question_prompt", sa.Text(), nullable=False),
        sa.Column("question_correct_answer", sa.Text(), nullable=False),
        sa.Column("question_options", json_type, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="teaching"),
        sa.Column("turns", json_type, nullable=False),
        sa.Column("nova_answer", sa.Text(), nullable=True),
        sa.Column("nova_score", sa.Integer(), nullable=True),
        sa.Column("nova_reasoning", sa.Text(), nullable=True),
        sa.Column("retakes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teachback_sessions_user_id", "teachback_sessions", ["user_id"])
    op.create_index("ix_teachback_sessions_topic_tag", "teachback_sessions", ["topic_tag"])
    op.create_index("ix_teachback_sessions_status", "teachback_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_teachback_sessions_status", table_name="teachback_sessions")
    op.drop_index("ix_teachback_sessions_topic_tag", table_name="teachback_sessions")
    op.drop_index("ix_teachback_sessions_user_id", table_name="teachback_sessions")
    op.drop_table("teachback_sessions")
