"""Drop teachback_sessions - the Teach-Back mode was removed.

Teach-Back graded the student by how an AI playing a confused classmate
reacted, not by anything the student answered, so it was taken out. The live
tutor and the chat tutor remain. Downgrade recreates the empty table.

Revision ID: 0012_drop_teachback
Revises: 0011_misconception_question
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_drop_teachback"
down_revision: Union[str, None] = "0011_misconception_question"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_teachback_sessions_status", table_name="teachback_sessions")
    op.drop_index("ix_teachback_sessions_topic_tag", table_name="teachback_sessions")
    op.drop_index("ix_teachback_sessions_user_id", table_name="teachback_sessions")
    op.drop_table("teachback_sessions")


def downgrade() -> None:
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
