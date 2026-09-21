"""lesson_progress table.

OWNER: Member 2. Schema: plan.md §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.course import Lesson
    from app.models.user import User


class LessonProgress(Base):
    """User progress and completion tracking for lessons."""

    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),
    )

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
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_started",  # 'not_started' | 'in_progress' | 'completed'
    )
    seconds_spent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[User | None] = relationship("User")
    lesson: Mapped[Lesson | None] = relationship("Lesson")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "lesson_id": str(self.lesson_id),
            "status": self.status,
            "seconds_spent": self.seconds_spent,
            "last_position": self.last_position,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

