"""Gamification models: user_stats, xp_events, badges, user_badges, daily_challenges, user_challenges, notifications.

OWNER: Member 4 (Gamification & Analytics).
SCHEMA: plan.md §3.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class UserStats(Base):
    """Aggregated gamification stats for a learner.

    Tracks XP, level, coin balance, streaks, and learning duration.
    """

    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    coins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_learning_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    user: Mapped[Any] = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "xp": self.xp,
            "level": self.level,
            "coins": self.coins,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_active_date": self.last_active_date.isoformat() if self.last_active_date else None,
            "total_learning_seconds": self.total_learning_seconds,
        }


class XPEvent(Base):
    """Immutable ledger of every XP award in the application.

    This table serves as the single source of truth for analytics, auditability,
    and anti-cheat verification. Never mutate UserStats.xp without recording
    an XPEvent row.
    """

    __tablename__ = "xp_events"

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
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    user: Mapped[Any] = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "event_type": self.event_type,
            "xp_awarded": self.xp_awarded,
            "ref_type": self.ref_type,
            "ref_id": str(self.ref_id) if self.ref_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Badge(Base):
    """Available badges in the gamification system."""

    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criteria: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    user_badges: Mapped[list[UserBadge]] = relationship("UserBadge", back_populates="badge", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "criteria": self.criteria,
            "xp_reward": self.xp_reward,
        }


class UserBadge(Base):
    """Mapping of earned badges per user."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
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
    badge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[Any] = relationship("User")
    badge: Mapped[Badge] = relationship("Badge", back_populates="user_badges")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "badge_id": str(self.badge_id),
            "earned_at": self.earned_at.isoformat() if self.earned_at else None,
        }


class DailyChallenge(Base):
    """Daily challenge templates pool."""

    __tablename__ = "daily_challenges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    challenge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    user_challenges: Mapped[list[UserChallenge]] = relationship(
        "UserChallenge", back_populates="challenge", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "date": self.date.isoformat() if self.date else None,
            "title": self.title,
            "description": self.description,
            "challenge_type": self.challenge_type,
            "target_value": self.target_value,
            "xp_reward": self.xp_reward,
            "coin_reward": self.coin_reward,
        }


class UserChallenge(Base):
    """User progress against a daily challenge."""

    __tablename__ = "user_challenges"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_user_challenges_user_challenge"),
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
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    progress_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[Any] = relationship("User")
    challenge: Mapped[DailyChallenge] = relationship("DailyChallenge", back_populates="user_challenges")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "challenge_id": str(self.challenge_id),
            "progress_value": self.progress_value,
            "is_completed": self.is_completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Notification(Base):
    """In-app notifications (badges, level ups, reminders)."""

    __tablename__ = "notifications"

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
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    user: Mapped[Any] = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
