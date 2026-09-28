"""Review queue question tracking + practice problems.

review_items.question_id
  The queue schedules topics, not questions, so the question asked for a topic
  changes between reviews. Recording which one was shown means an answer is
  graded against the question the student actually saw.

practice_problems / practice_test_cases / practice_submissions
  SQL exercises graded by running them. Until now the Practice UI had no backend
  at all and fell back to client-side "grading" that passed any code longer than
  15 characters and reported a randomised runtime. See services/sql_runner.py.

Revision ID: 0010_review_and_practice
Revises: 0009_m1_topics_and_jobs
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_review_and_practice"
down_revision: Union[str, None] = "0009_m1_topics_and_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    op.add_column("review_items", sa.Column("question_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_review_items_question_id",
        "review_items",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "practice_problems",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("topic_tag", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="easy"),
        sa.Column("statement_md", sa.Text(), nullable=False),
        sa.Column("input_format", sa.Text(), nullable=True),
        sa.Column("output_format", sa.Text(), nullable=True),
        sa.Column("constraints", json_type, nullable=False),
        sa.Column("examples", json_type, nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference_sql", sa.Text(), nullable=False),
        sa.Column("order_matters", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_problems_slug", "practice_problems", ["slug"], unique=True)
    op.create_index("ix_practice_problems_topic_tag", "practice_problems", ["topic_tag"])

    op.create_table(
        "practice_test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("setup_sql", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["problem_id"], ["practice_problems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_test_cases_problem_id", "practice_test_cases", ["problem_id"])

    op.create_table(
        "practice_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("all_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["practice_problems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_submissions_user_id", "practice_submissions", ["user_id"])
    op.create_index("ix_practice_submissions_problem_id", "practice_submissions", ["problem_id"])
    op.create_index("ix_practice_submissions_created_at", "practice_submissions", ["created_at"])


def downgrade() -> None:
    op.drop_table("practice_submissions")
    op.drop_table("practice_test_cases")
    op.drop_index("ix_practice_problems_topic_tag", table_name="practice_problems")
    op.drop_index("ix_practice_problems_slug", table_name="practice_problems")
    op.drop_table("practice_problems")
    op.drop_constraint("fk_review_items_question_id", "review_items", type_="foreignkey")
    op.drop_column("review_items", "question_id")
