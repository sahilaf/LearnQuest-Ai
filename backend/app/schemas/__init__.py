"""Pydantic request/response models.

Split by domain, mirroring models/. Standard error shape (plan.md 4.2):
    {"detail": "Human readable message", "code": "QUIZ_NOT_FOUND"}
Standard list shape:
    {"items": [...], "total": 137, "page": 1, "page_size": 20}
"""

from app.schemas.admin import AdminOverviewResponse
from app.schemas.common import ErrorResponse, Page
from app.schemas.course import (
    CourseCreate,
    CourseDetailResponse,
    CourseResponse,
    CourseUpdate,
    EnrollmentResponse,
    LessonCreate,
    LessonResponse,
    LessonUpdate,
)
from app.schemas.upload import UploadResponse
from app.schemas.user import (
    AdminUserUpdate,
    SyncUserResponse,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)

__all__ = [
    "AdminOverviewResponse",
    "AdminUserUpdate",
    "CourseCreate",
    "CourseDetailResponse",
    "CourseResponse",
    "CourseUpdate",
    "EnrollmentResponse",
    "ErrorResponse",
    "LessonCreate",
    "LessonResponse",
    "LessonUpdate",
    "Page",
    "SyncUserResponse",
    "UploadResponse",
    "UserProfileResponse",
    "UserResponse",
    "UserUpdate",
]
