"""Course catalog and enrollment.

OWNER: Member 2 (reads) / Member 3 (writes). See plan.md §7.3.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import database_is_configured, get_db
from app.deps import CurrentUser
from app.models.course import Course, Enrollment, Lesson
from app.schemas.course import CourseDetailResponse, CourseResponse, EnrollmentResponse
from app.services.events import emit

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=dict[str, Any])
def list_courses(
    search: str | None = None,
    subject: str | None = None,
    difficulty: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Published courses, filterable. Public - no auth required."""
    if not db or not database_is_configured():
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    query = db.query(Course).filter(Course.is_published.is_(True))

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Course.title.ilike(search_filter),
                Course.description.ilike(search_filter),
                Course.subject.ilike(search_filter),
            )
        )
    if subject:
        query = query.filter(Course.subject.ilike(subject.strip()))
    if difficulty:
        query = query.filter(Course.difficulty.ilike(difficulty.strip()))

    total = query.count()
    courses = (
        query.order_by(Course.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [CourseResponse.model_validate(c.to_dict()).model_dump() for c in courses]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{slug}", response_model=CourseDetailResponse)
def get_course(
    slug: str,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Course detail with its ordered lesson list."""
    if not db or not database_is_configured():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    # Allow lookup by slug or by UUID
    course = None
    try:
        course_uuid = uuid.UUID(slug)
        course = (
            db.query(Course)
            .options(joinedload(Course.lessons))
            .filter(Course.id == course_uuid)
            .first()
        )
    except ValueError:
        pass

    if not course:
        course = (
            db.query(Course)
            .options(joinedload(Course.lessons))
            .filter(Course.slug == slug)
            .first()
        )

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{slug}' not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    return course.to_dict(include_lessons=True)


@router.post("/{course_id}/enroll")
def enroll(
    course_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Enroll the current user in a course and emit course.enrolled."""
    if not db or not database_is_configured():
        return {"course_id": course_id, "enrolled": True}

    try:
        c_uuid = uuid.UUID(course_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course ID.",
            headers={"X-Error-Code": "INVALID_COURSE_ID"},
        ) from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    user_uuid = uuid.UUID(user["id"])
    existing = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user_uuid, Enrollment.course_id == c_uuid)
        .first()
    )

    if existing:
        return {
            "course_id": str(course.id),
            "enrolled": True,
            "already_enrolled": True,
            "enrollment_id": str(existing.id),
        }

    enrollment = Enrollment(user_id=user_uuid, course_id=c_uuid)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    emit(db, user_uuid, "course.enrolled", {"course_id": str(course.id)})

    return {
        "course_id": str(course.id),
        "enrolled": True,
        "already_enrolled": False,
        "enrollment_id": str(enrollment.id),
    }
