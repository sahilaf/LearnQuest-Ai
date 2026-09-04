"""Pydantic schemas for User and Auth domain.

OWNER: Member 3. See plan.md §4.2, §8.3.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserPreferences(BaseModel):
    model_config = ConfigDict(extra="allow")

    tutor_tone: str = Field(default="encouraging", description="encouraging | concise | socratic")
    difficulty_pref: str = Field(default="adaptive", description="beginner | intermediate | advanced | adaptive")
    daily_goal_minutes: int = Field(default=20, ge=5, le=180)
    timezone: str = Field(default="UTC")


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    preferences: dict[str, Any] | None = None


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(student|admin)$")
    full_name: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    role: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserProfileResponse(BaseModel):
    user: UserResponse
    stats: dict[str, Any] | None = None


class SyncUserResponse(BaseModel):
    user: UserResponse
    created: bool = False
