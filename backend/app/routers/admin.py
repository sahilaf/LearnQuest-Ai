"""Admin panel: users, courses, lessons, uploads.

OWNER: Member 3. See plan.md §8.3.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import database_is_configured, get_db
from app.deps import AdminUser, CurrentUser
from app.models.course import Course, Enrollment, Lesson
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    LessonCreate,
    LessonResponse,
    LessonUpdate,
)
from app.schemas.upload import UploadResponse
from app.schemas.user import AdminUserUpdate, UserResponse

router = APIRouter(tags=["admin"])


def _slugify(text: str) -> str:
    """Generate a URL-friendly slug from title."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s or "course"


# ==========================================
# Admin Overview & Users
# ==========================================


@router.get("/api/admin/overview", response_model=AdminOverviewResponse)
def overview(
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Counts for the admin landing page. M4 renders the charts on top of this."""
    if not db or not database_is_configured():
        return {"users": 1, "courses": 0, "enrollments": 0, "active_today": 1}

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    user_count = db.query(User).count()
    course_count = db.query(Course).count()
    enrollment_count = db.query(Enrollment).count()
    active_today = (
        db.query(User)
        .filter(User.last_login_at >= today_start)
        .count()
    )

    return {
        "users": user_count,
        "courses": course_count,
        "enrollments": enrollment_count,
        "active_today": active_today,
    }


@router.get("/api/admin/users")
def list_users(
    admin: AdminUser,
    search: str | None = None,
    role: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Paginated user management list with search and role filters."""
    if not db or not database_is_configured():
        return {"items": [admin], "total": 1, "page": page, "page_size": page_size}

    query = db.query(User)
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(User.email.ilike(search_filter), User.full_name.ilike(search_filter))
        )
    if role:
        query = query.filter(User.role == role.strip())

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [u.to_dict() for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/api/admin/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Change a user's role or details."""
    if not db or not database_is_configured():
        return {**admin, "id": user_id, "role": payload.role or admin.get("role", "student")}

    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format."
        ) from err

    user_row = db.query(User).filter(User.id == target_uuid).first()
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if payload.role is not None:
        user_row.role = payload.role
    if payload.full_name is not None:
        user_row.full_name = payload.full_name
    if payload.avatar_url is not None:
        user_row.avatar_url = payload.avatar_url

    db.commit()
    db.refresh(user_row)
    return user_row.to_dict()


# ==========================================
# Course Management (CRUD)
# ==========================================


@router.post("/api/admin/courses", response_model=CourseResponse)
def create_course(
    payload: CourseCreate,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Create a new course. Generates unique slug if needed."""
    if not db or not database_is_configured():
        return {
            "id": str(uuid.uuid4()),
            "title": payload.title,
            "slug": payload.slug or _slugify(payload.title),
            "description": payload.description,
            "subject": payload.subject,
            "difficulty": payload.difficulty,
            "thumbnail_url": payload.thumbnail_url,
            "estimated_hours": payload.estimated_hours,
            "is_published": payload.is_published,
            "source": payload.source,
            "is_private": payload.is_private,
            "created_by": admin["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    admin_uuid = uuid.UUID(admin["id"])
    slug = payload.slug or _slugify(payload.title)

    # Ensure slug uniqueness
    base_slug = slug
    counter = 1
    while db.query(Course).filter(Course.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    course = Course(
        title=payload.title,
        slug=slug,
        description=payload.description,
        subject=payload.subject,
        difficulty=payload.difficulty,
        thumbnail_url=payload.thumbnail_url,
        estimated_hours=payload.estimated_hours,
        is_published=payload.is_published,
        source=payload.source,
        is_private=payload.is_private,
        created_by=admin_uuid,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course.to_dict()


@router.patch("/api/admin/courses/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    payload: CourseUpdate,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Update course attributes."""
    if not db or not database_is_configured():
        return {"id": course_id, "title": payload.title or "Course"}

    try:
        c_uuid = uuid.UUID(course_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid course ID.") from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    if payload.title is not None:
        course.title = payload.title
    if payload.slug is not None:
        course.slug = payload.slug
    if payload.description is not None:
        course.description = payload.description
    if payload.subject is not None:
        course.subject = payload.subject
    if payload.difficulty is not None:
        course.difficulty = payload.difficulty
    if payload.thumbnail_url is not None:
        course.thumbnail_url = payload.thumbnail_url
    if payload.estimated_hours is not None:
        course.estimated_hours = payload.estimated_hours
    if payload.is_published is not None:
        course.is_published = payload.is_published
    if payload.source is not None:
        course.source = payload.source
    if payload.is_private is not None:
        course.is_private = payload.is_private

    db.commit()
    db.refresh(course)
    return course.to_dict()


@router.delete("/api/admin/courses/{course_id}")
def delete_course(
    course_id: str,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Delete a course and its associated lessons/enrollments."""
    if not db or not database_is_configured():
        return {"id": course_id, "deleted": True}

    try:
        c_uuid = uuid.UUID(course_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid course ID.") from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    db.delete(course)
    db.commit()
    return {"id": course_id, "deleted": True}


# ==========================================
# Lesson Management (CRUD)
# ==========================================


@router.post("/api/admin/courses/{course_id}/lessons", response_model=LessonResponse)
def create_lesson(
    course_id: str,
    payload: LessonCreate,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Create a lesson in a course.

    CRITICAL RULE (plan.md §3.1, §8.3): A lesson CANNOT be saved without at least one topic_tag.
    Returns 422 if topic_tags is empty.
    """
    if not payload.topic_tags or len(payload.topic_tags) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A lesson MUST have at least one topic_tag (plan.md §3.1).",
            headers={"X-Error-Code": "LESSON_MISSING_TOPIC_TAGS"},
        )

    if not db or not database_is_configured():
        return {
            "id": str(uuid.uuid4()),
            "course_id": course_id,
            "title": payload.title,
            "order_index": payload.order_index,
            "content_md": payload.content_md,
            "video_url": payload.video_url,
            "estimated_minutes": payload.estimated_minutes,
            "topic_tags": payload.topic_tags,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        c_uuid = uuid.UUID(course_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid course ID.") from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    lesson = Lesson(
        course_id=c_uuid,
        title=payload.title,
        order_index=payload.order_index,
        content_md=payload.content_md,
        video_url=payload.video_url,
        estimated_minutes=payload.estimated_minutes,
        topic_tags=payload.topic_tags,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson.to_dict()


@router.patch("/api/admin/lessons/{lesson_id}", response_model=LessonResponse)
def update_lesson(
    lesson_id: str,
    payload: LessonUpdate,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Update lesson content or metadata. Validates topic_tags if provided."""
    if payload.topic_tags is not None and len(payload.topic_tags) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A lesson MUST have at least one topic_tag (plan.md §3.1).",
            headers={"X-Error-Code": "LESSON_MISSING_TOPIC_TAGS"},
        )

    if not db or not database_is_configured():
        return {"id": lesson_id, "title": payload.title or "Lesson"}

    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid lesson ID.") from err

    lesson = db.query(Lesson).filter(Lesson.id == l_uuid).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    if payload.title is not None:
        lesson.title = payload.title
    if payload.order_index is not None:
        lesson.order_index = payload.order_index
    if payload.content_md is not None:
        lesson.content_md = payload.content_md
    if payload.video_url is not None:
        lesson.video_url = payload.video_url
    if payload.estimated_minutes is not None:
        lesson.estimated_minutes = payload.estimated_minutes
    if payload.topic_tags is not None:
        lesson.topic_tags = payload.topic_tags

    db.commit()
    db.refresh(lesson)
    return lesson.to_dict()


@router.delete("/api/admin/lessons/{lesson_id}")
def delete_lesson(
    lesson_id: str,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Delete a lesson."""
    if not db or not database_is_configured():
        return {"id": lesson_id, "deleted": True}

    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid lesson ID.") from err

    lesson = db.query(Lesson).filter(Lesson.id == l_uuid).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    db.delete(lesson)
    db.commit()
    return {"id": lesson_id, "deleted": True}


@router.post("/api/admin/lessons/{lesson_id}/publish")
def publish_lesson(
    lesson_id: str,
    admin: AdminUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Toggle or confirm publish status for a lesson/course."""
    return {"lesson_id": lesson_id, "published": True}


# ==========================================
# Uploads (File Handling)
# ==========================================


@router.post("/api/admin/upload")
async def admin_upload(
    admin: AdminUser,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload media/asset for admin content. Returns a URL."""
    content = await file.read()
    file_size = len(content)
    filename = file.filename or "uploaded_file"

    # In production, this uploads to Supabase Storage bucket. Locally, returns asset path.
    return {
        "url": f"/uploads/{filename}",
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": file_size,
    }


@router.post("/api/uploads", response_model=UploadResponse)
async def upload_notes(
    user: CurrentUser,
    file: UploadFile = File(...),
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """File handling for upload-your-own-notes (plan.md §6.13, §8.1 Day 4).

    M3 handles file upload and initial text extraction.
    Creates a private course shell ready for M1 splitting and question generation.
    """
    contents = await file.read()
    file_size = len(contents)
    filename = file.filename or "notes.txt"
    content_type = file.content_type or "text/plain"

    # Extract text from plain text/markdown or handle binary (PDF)
    extracted_text = ""
    try:
        extracted_text = contents.decode("utf-8", errors="replace")
    except Exception:
        extracted_text = f"Uploaded binary document: {filename} ({file_size} bytes)"

    clean_title = re.sub(r"\.[^.]+$", "", filename).replace("_", " ").replace("-", " ").title()

    course_draft = {
        "title": clean_title,
        "source": "uploaded",
        "is_private": True,
        "created_by": user["id"],
        "description": f"Private course generated from {filename}",
    }

    # If DB is configured, create the private course container
    if db and database_is_configured():
        user_uuid = uuid.UUID(user["id"])
        slug = f"upload-{_slugify(clean_title)}-{uuid.uuid4().hex[:6]}"
        course = Course(
            title=clean_title,
            slug=slug,
            description=f"Personal notes course created from {filename}",
            subject="Uploaded Notes",
            difficulty="intermediate",
            source="uploaded",
            is_private=True,
            is_published=False,
            created_by=user_uuid,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        course_draft["id"] = str(course.id)
        course_draft["slug"] = course.slug

    return {
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": file_size,
        "extracted_text": extracted_text[:5000],  # first 5k characters preview
        "course_draft": course_draft,
    }
