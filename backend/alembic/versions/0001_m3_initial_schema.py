"""m3: initial schema for users, courses, lessons, enrollments

Revision ID: 0001_m3_initial_schema
Revises: 
Create Date: 2026-09-03 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_m3_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- users table ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="student"),
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Supabase auth.users foreign key (PostgreSQL only)
    if is_postgres:
        op.create_foreign_key(
            "fk_users_auth",
            "users",
            "users",
            ["id"],
            ["id"],
            referent_schema="auth",
            ondelete="CASCADE",
        )

    # --- courses table ---
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=50), nullable=False, server_default="beginner"),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("estimated_hours", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="seeded"),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)

    # --- lessons table ---
    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("video_url", sa.String(length=1024), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "topic_tags",
            postgresql.ARRAY(sa.String(length=100)) if is_postgres else sa.JSON(),
            nullable=False,
            server_default="{}" if is_postgres else "[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lessons_course_id", "lessons", ["course_id"], unique=False)

    # --- enrollments table ---
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_user_course_enrollment"),
    )
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"], unique=False)
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"], unique=False)


def downgrade() -> None:
    op.drop_table("enrollments")
    op.drop_table("lessons")
    op.drop_table("courses")
    op.drop_table("users")
