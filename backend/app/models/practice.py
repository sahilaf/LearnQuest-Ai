"""Practice problems: SQL exercises graded by actually running them.

OWNER: Member 2 (UI) / Member 1 (runner). See services/sql_runner.py.

A problem carries a REFERENCE solution and several test cases, each with its own
seed data. Grading runs both the reference and the student's query against the
same seed and compares result sets - so expected output is never hand-written,
and never wrong in a way that disagrees with the reference.

`reference_sql` and each case's `setup_sql` are never sent to the client. The
first would give the answer away; the second would let a student fit their
query to the hidden cases instead of writing a correct one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

JSON_VARIANT = JSONB().with_variant(JSON, "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PracticeProblem(Base):
    __tablename__ = "practice_problems"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="easy")
    statement_md: Mapped[str] = mapped_column(Text, nullable=False)
    input_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[list[str]] = mapped_column(JSON_VARIANT, nullable=False, default=list)
    # Worked examples shown to the student. Illustrative only - grading uses
    # the test cases, not these.
    examples: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_VARIANT, nullable=False, default=list
    )
    starter_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Never sent to the client.
    reference_sql: Mapped[str] = mapped_column(Text, nullable=False)
    # When false, rows are compared as a multiset: a correct query without an
    # ORDER BY should not fail because the engine returned rows differently.
    order_matters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    test_cases: Mapped[list[PracticeTestCase]] = relationship(
        "PracticeTestCase",
        back_populates="problem",
        order_by="PracticeTestCase.position",
        cascade="all, delete-orphan",
    )


class PracticeTestCase(Base):
    __tablename__ = "practice_test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("practice_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Hidden cases are the edge cases - the customer with no orders, the tie in
    # the sort. Showing them lets a student pass by special-casing.
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Never sent to the client.
    setup_sql: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    problem: Mapped[PracticeProblem] = relationship(
        "PracticeProblem", back_populates="test_cases"
    )


class PracticeSubmission(Base):
    __tablename__ = "practice_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("practice_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    all_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_VARIANT, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )
