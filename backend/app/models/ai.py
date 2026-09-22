"""AI and tutoring models: conversations, messages, topic_mastery, review_items, recommendations.

OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
SCHEMA: plan.md §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


JSON_VARIANT = JSONB().with_variant(JSON, "sqlite")


class Conversation(Base):
    """A chat thread between a student and the AI tutor."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "number", name="uq_conversations_user_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The conversation's public identifier, counting from 1 per user, so the
    # tutor lives at /tutor/7 rather than at a 36-character primary key. The
    # UUID stays the real key - this is only what the URL shows, and because it
    # is scoped to one user it leaks nothing about anyone else's activity.
    number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="New conversation"
    )
    context_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    context_course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Rolling summary = long-term memory
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "number": self.number,
            "user_id": str(self.user_id),
            "title": self.title,
            "context_lesson_id": str(self.context_lesson_id) if self.context_lesson_id else None,
            "context_course_id": str(self.context_course_id) if self.context_course_id else None,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(Base):
    """An individual message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visemes: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON_VARIANT, nullable=True
    )  # [{"t": 0.00, "v": "sil"}, {"t": 0.08, "v": "AA"}]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role,
            "content": self.content,
            "tokens": self.tokens,
            "audio_url": self.audio_url,
            "visemes": self.visemes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TopicMastery(Base):
    """Student mastery and tracked misconceptions for each topic tag."""

    __tablename__ = "topic_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "topic_tag", name="uq_topic_mastery_user_topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mastery_score: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.5
    )  # 0.000 .. 1.000
    misconception: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Plain English description of false belief
    misconception_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Consecutive correct answers since the misconception was captured. Drives
    # the active -> fading -> cleared decay in services/mastery.py.
    misconception_correct_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Set when the streak clears it. The text is deliberately kept so the
    # misconception map can show what a student has overcome, not only what
    # they still get wrong.
    misconception_cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "topic_tag": self.topic_tag,
            "mastery_score": float(self.mastery_score) if self.mastery_score is not None else 0.5,
            "misconception": self.misconception,
            "misconception_updated_at": (
                self.misconception_updated_at.isoformat()
                if self.misconception_updated_at
                else None
            ),
            "misconception_correct_streak": self.misconception_correct_streak or 0,
            "misconception_cleared_at": (
                self.misconception_cleared_at.isoformat()
                if self.misconception_cleared_at
                else None
            ),
            "attempts": self.attempts,
            "correct": self.correct,
            "last_practiced_at": (
                self.last_practiced_at.isoformat() if self.last_practiced_at else None
            ),
        }


class ReviewItem(Base):
    """Spaced repetition daily review queue item."""

    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "topic_tag", "source_lesson_id", name="uq_review_items_user_topic_lesson"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    source_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "topic_tag": self.topic_tag,
            "source_lesson_id": str(self.source_lesson_id) if self.source_lesson_id else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "interval_days": self.interval_days,
            "streak": self.streak,
            "last_reviewed_at": (
                self.last_reviewed_at.isoformat() if self.last_reviewed_at else None
            ),
        }


class Recommendation(Base):
    """Personalized learning recommendation for a student."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # lesson | revision | quiz | challenge
    target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.5
    )
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "kind": self.kind,
            "target_id": str(self.target_id),
            "reason": self.reason,
            "score": float(self.score) if self.score is not None else 0.5,
            "is_dismissed": self.is_dismissed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class TeachBackSession(Base):
    """One Teach-Back round: the student teaches Nova out of their own misconception.

    The protege effect, made literal. Nova is seeded with the false belief this
    student actually holds, argues from it, and then re-takes the question they
    got wrong. Nova's score on that retry is the student's grade - you have only
    taught something when the learner can use it without you.

    State lives in one row rather than in the chat transcript because the grade
    has to be reconstructible: `question_prompt` and `question_correct_answer`
    are snapshotted at start so a later edit to the question cannot change a
    grade that was already awarded.
    """

    __tablename__ = "teachback_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Snapshot of the misconception as it read when the session opened. The
    # TopicMastery row may be cleared or overwritten before this session ends.
    misconception: Mapped[str] = mapped_column(Text, nullable=False)

    # The question Nova will re-take, snapshotted for the same reason.
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    question_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    question_options: Mapped[list[str] | None] = mapped_column(
        JSON_VARIANT, nullable=True
    )

    # teaching | passed | failed | abandoned
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="teaching", index=True
    )

    # [{"role": "nova" | "student", "content": "...", "at": "iso8601"}]
    turns: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_VARIANT, nullable=False, default=list
    )

    # Result of the most recent retake.
    nova_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    nova_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nova_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    retakes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self, include_answer: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(self.id),
            "topic_tag": self.topic_tag,
            "misconception": self.misconception,
            "question_prompt": self.question_prompt,
            "question_options": self.question_options,
            "status": self.status,
            "turns": self.turns or [],
            "nova_answer": self.nova_answer,
            "nova_score": self.nova_score,
            "nova_reasoning": self.nova_reasoning,
            "retakes": self.retakes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }
        # The correct answer is the thing the student is being asked to teach.
        # Showing it mid-session turns teaching into copying, so it is released
        # only once the session is over.
        if include_answer or self.status in ("passed", "failed"):
            data["question_correct_answer"] = self.question_correct_answer
        return data
