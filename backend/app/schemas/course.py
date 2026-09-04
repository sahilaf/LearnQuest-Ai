"""Pydantic schemas for Course, Lesson, and Enrollment domain.

OWNER: Member 3. See plan.md §3.1, §4.2, §8.3.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LessonBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    order_index: int = Field(default=1, ge=1)
    content_md: str = Field(default="")
    video_url: str | None = None
    estimated_minutes: int = Field(default=10, ge=1, le=240)
    topic_tags: list[str] = Field(
        ...,
        description="CRITICAL: drives mastery and recommendations. Must contain at least one tag.",
    )

    @field_validator("topic_tags")
    @classmethod
    def validate_topic_tags(cls, v: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]
        if not cleaned:
            raise ValueError(
                "A lesson MUST have at least one topic_tag (plan.md §3.1). "
                "M1's recommender is blind without it."
            )
        return cleaned


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    order_index: int | None = Field(default=None, ge=1)
    content_md: str | None = None
    video_url: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=240)
    topic_tags: list[str] | None = None

    @field_validator("topic_tags")
    @classmethod
    def validate_topic_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            cleaned = [tag.strip() for tag in v if tag and tag.strip()]
            if not cleaned:
                raise ValueError("A lesson cannot have empty topic_tags.")
            return cleaned
        return v


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    course_id: str | UUID
    title: str
    order_index: int
    content_md: str
    video_url: str | None = None
    estimated_minutes: int
    topic_tags: list[str]
    created_at: datetime | None = None


class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    subject: str | None = None
    difficulty: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")
    thumbnail_url: str | None = None
    estimated_hours: int = Field(default=1, ge=1)
    is_published: bool = False
    source: str = Field(default="seeded", pattern="^(seeded|uploaded)$")
    is_private: bool = False


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = None
    subject: str | None = None
    difficulty: str | None = Field(default=None, pattern="^(beginner|intermediate|advanced)$")
    thumbnail_url: str | None = None
    estimated_hours: int | None = Field(default=None, ge=1)
    is_published: bool | None = None
    source: str | None = None
    is_private: bool | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    title: str
    slug: str
    description: str | None = None
    subject: str | None = None
    difficulty: str
    thumbnail_url: str | None = None
    estimated_hours: int
    is_published: bool
    source: str
    is_private: bool
    created_by: str | UUID | None = None
    created_at: datetime | None = None


class CourseDetailResponse(CourseResponse):
    lessons: list[LessonResponse] = Field(default_factory=list)


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    user_id: str | UUID
    course_id: str | UUID
    enrolled_at: datetime
    completed_at: datetime | None = None
    course: CourseResponse | None = None
