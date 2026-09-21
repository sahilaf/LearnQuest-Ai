"""Pydantic schemas for Lesson Progress and History domain.

OWNER: Member 2. See plan.md §3, §4.2, §7.3.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProgressUpdateRequest(BaseModel):
    """Payload sent during heartbeat or lesson completion."""

    status: str = Field(
        default="in_progress",
        description="not_started | in_progress | completed",
    )
    seconds_spent: int = Field(default=0, ge=0)
    last_position: int = Field(default=0, ge=0)


class LessonProgressResponse(BaseModel):
    """Progress status for a user on a given lesson."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    lesson_id: UUID
    status: str
    seconds_spent: int
    last_position: int
    completed_at: datetime | None = None


class CourseProgressResponse(BaseModel):
    """Aggregated course progress statistics."""

    course_id: str | UUID
    course_title: str
    course_slug: str
    subject: str | None = None
    difficulty: str | None = None
    completed_lessons: int
    total_lessons: int
    completion_percentage: float
    completed_lesson_ids: list[str] = Field(default_factory=list)
    in_progress_lesson_ids: list[str] = Field(default_factory=list)
    next_lesson_id: str | UUID | None = None
    next_lesson_title: str | None = None
    enrolled_at: datetime | None = None
    completed_at: datetime | None = None


class HistoryItemResponse(BaseModel):
    """Timeline entry in the user's learning history."""

    id: str | UUID
    item_type: str = Field(..., description="'lesson' or 'quiz'")
    title: str
    course_id: str | UUID | None = None
    course_title: str | None = None
    lesson_id: str | UUID | None = None
    quiz_id: str | UUID | None = None
    attempt_id: str | UUID | None = None
    status: str
    score: float | None = None
    passed: bool | None = None
    seconds_spent: int | None = None
    completed_at: datetime
