"""m2: learning management schema for lesson_progress, quizzes, questions, quiz_attempts, attempt_answers

Revision ID: 0006_m2_learning_management
Revises: 0005_m1_misconception_tracking
Create Date: 2026-09-21 08:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_m2_learning_management"
down_revision: Union[str, None] = "0005_m1_misconception_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    # --- lesson_progress table ---
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="not_started"),
        sa.Column("seconds_spent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )
    op.create_index("ix_lesson_progress_user_id", "lesson_progress", ["user_id"])
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"])

    # --- quizzes table ---
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("difficulty", sa.String(length=50), nullable=True, server_default="beginner"),
        sa.Column("generated_by_user", sa.Uuid(), nullable=True),
        sa.Column("topic_tags", json_type, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_by_user"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quizzes_lesson_id", "quizzes", ["lesson_id"])
    op.create_index("ix_quizzes_course_id", "quizzes", ["course_id"])

    # --- questions table ---
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False, server_default="mcq"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", json_type, nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("topic_tag", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=50), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_quiz_id", "questions", ["quiz_id"])
    op.create_index("ix_questions_topic_tag", "questions", ["topic_tag"])

    # --- quiz_attempts table ---
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])

    # --- attempt_answers table ---
    op.create_table(
        "attempt_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("topic_tag", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attempt_answers_attempt_id", "attempt_answers", ["attempt_id"])
    op.create_index("ix_attempt_answers_question_id", "attempt_answers", ["question_id"])
    op.create_index("ix_attempt_answers_topic_tag", "attempt_answers", ["topic_tag"])


def downgrade() -> None:
    op.drop_table("attempt_answers")
    op.drop_table("quiz_attempts")
    op.drop_table("questions")
    op.drop_table("quizzes")
    op.drop_table("lesson_progress")
