"""courses, lessons, enrollments tables.

OWNER: Member 3. Schema: plan.md §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Course(Base):
    """Course entity in the catalog."""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="beginner",  # 'beginner' | 'intermediate' | 'advanced'
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="seeded",  # 'seeded' | 'uploaded'
    )
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    creator: Mapped[User | None] = relationship("User", back_populates="created_courses")
    lessons: Mapped[list[Lesson]] = relationship(
        "Lesson",
        back_populates="course",
        order_by="Lesson.order_index",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment",
        back_populates="course",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_lessons: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(self.id),
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "subject": self.subject,
            "difficulty": self.difficulty,
            "thumbnail_url": self.thumbnail_url,
            "estimated_hours": self.estimated_hours,
            "is_published": self.is_published,
            "source": self.source,
            "is_private": self.is_private,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_lessons:
            data["lessons"] = [l.to_dict() for l in self.lessons]
        return data


class Lesson(Base):
    """Lesson entity within a course.

    CRITICAL RULE (plan.md §3.1): topic_tags drives mastery and recommendations.
    Every lesson must have at least one topic_tag.
    """

    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    video_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    topic_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    course: Mapped[Course] = relationship("Course", back_populates="lessons")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "course_id": str(self.course_id),
            "title": self.title,
            "order_index": self.order_index,
            "content_md": self.content_md,
            "video_url": self.video_url,
            "estimated_minutes": self.estimated_minutes,
            "topic_tags": self.topic_tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Enrollment(Base):
    """User enrollment in a course."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_user_course_enrollment"),
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
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="enrollments")
    course: Mapped[Course] = relationship("Course", back_populates="enrollments")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "course_id": str(self.course_id),
            "enrolled_at": self.enrolled_at.isoformat() if self.enrolled_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
