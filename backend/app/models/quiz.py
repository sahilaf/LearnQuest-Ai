"""quizzes, questions, quiz_attempts, attempt_answers tables.

OWNER: Member 2 (attempts) and Member 1 (AI-generated questions). Schema: plan.md §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.course import Course, Lesson
    from app.models.user import User


class Quiz(Base):
    """Quiz container holding a set of practice questions."""

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",  # 'manual' | 'ai_generated'
    )
    difficulty: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="beginner",
    )
    generated_by_user: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    lesson: Mapped[Lesson | None] = relationship("Lesson")
    course: Mapped[Course | None] = relationship("Course")
    creator: Mapped[User | None] = relationship("User")
    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="quiz",
        order_by="Question.order_index",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
        "QuizAttempt",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_questions: bool = False, strip_answers: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(self.id),
            "lesson_id": str(self.lesson_id) if self.lesson_id else None,
            "course_id": str(self.course_id) if self.course_id else None,
            "title": self.title,
            "source": self.source,
            "difficulty": self.difficulty,
            "generated_by_user": str(self.generated_by_user) if self.generated_by_user else None,
            "topic_tags": self.topic_tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_questions:
            data["questions"] = [
                q.to_dict(strip_answers=strip_answers) for q in self.questions
            ]
        return data


class Question(Base):
    """Question item belonging to a quiz."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mcq",  # 'mcq' | 'true_false' | 'fill_blank' | 'short_answer'
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="questions")

    def to_dict(self, strip_answers: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(self.id),
            "quiz_id": str(self.quiz_id),
            "type": self.type,
            "prompt": self.prompt,
            "options": self.options,
            "topic_tag": self.topic_tag,
            "difficulty": self.difficulty,
            "order_index": self.order_index,
        }
        # Plan 7.3 security requirement: never return correct_answer or explanation pre-submit
        if not strip_answers:
            data["correct_answer"] = self.correct_answer
            data["explanation"] = self.explanation
        return data


class QuizAttempt(Base):
    """User attempt record for a quiz session."""

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.0,
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User")
    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="attempts")
    answers: Mapped[list[AttemptAnswer]] = relationship(
        "AttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_answers: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "quiz_id": str(self.quiz_id),
            "score": float(self.score) if self.score is not None else 0.0,
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "duration_seconds": self.duration_seconds,
        }
        if include_answers:
            data["answers"] = [a.to_dict() for a in self.answers]
        return data


class AttemptAnswer(Base):
    """User response to a specific question inside an attempt."""

    __tablename__ = "attempt_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Copied from questions.topic_tag at submit time so mastery can be recomputed without joining 4 tables
    topic_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="answers")
    question: Mapped[Question] = relationship("Question")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "attempt_id": str(self.attempt_id),
            "question_id": str(self.question_id),
            "user_answer": self.user_answer,
            "is_correct": self.is_correct,
            "topic_tag": self.topic_tag,
        }

