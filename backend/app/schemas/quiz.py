"""Pydantic schemas for Quiz, Question, and Attempt domain.

OWNER: Member 2 (consumption & attempts) / Member 1 (AI generation).
See plan.md §3, §4.2, §7.3.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionPublicResponse(BaseModel):
    """Question representation for test-takers pre-submission.

    SECURITY (plan.md §7.3): correct_answer and explanation MUST NEVER appear here.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    quiz_id: UUID
    type: str = Field(default="mcq", description="mcq | true_false | fill_blank | short_answer")
    prompt: str
    options: list[str] | None = None
    topic_tag: str | None = None
    difficulty: str | None = None
    order_index: int = 0


class QuizPublicResponse(BaseModel):
    """Quiz representation with sanitized questions."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lesson_id: UUID | None = None
    course_id: UUID | None = None
    title: str | None = None
    source: str = "manual"
    difficulty: str | None = "beginner"
    topic_tags: list[str] = Field(default_factory=list)
    questions: list[QuestionPublicResponse] = Field(default_factory=list)


class AttemptStartResponse(BaseModel):
    """Response returned when an attempt is initiated."""

    attempt_id: UUID
    quiz_id: UUID


class AnswerSubmit(BaseModel):
    """User response submitted for a single question."""

    question_id: UUID
    user_answer: str = Field(..., min_length=1)


class AttemptSubmitRequest(BaseModel):
    """Payload sent when submitting a completed quiz attempt."""

    answers: list[AnswerSubmit] = Field(default_factory=list)


class AttemptAnswerResultResponse(BaseModel):
    """Detailed question result visible only post-submission."""

    model_config = ConfigDict(from_attributes=True)

    question_id: UUID
    user_answer: str
    is_correct: bool
    correct_answer: str
    explanation: str | None = None
    topic_tag: str | None = None


class AttemptResultResponse(BaseModel):
    """Full quiz attempt review including score and per-question explanations."""

    model_config = ConfigDict(from_attributes=True)

    attempt_id: UUID
    quiz_id: UUID
    score: float
    total_questions: int
    correct_count: int
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    duration_seconds: int | None = None
    answers: list[AttemptAnswerResultResponse] = Field(default_factory=list)
