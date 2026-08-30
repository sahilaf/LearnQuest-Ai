"""Course catalog and enrollment.

OWNER: Member 2 (reads) / Member 3 (writes). See plan.md 7.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
def list_courses(
    search: str | None = None,
    subject: str | None = None,
    difficulty: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Published courses, filterable. Public - no auth required."""
    # TODO(M2): query courses where is_published is true.
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/{slug}")
def get_course(slug: str) -> dict:
    """Course detail with its ordered lesson list."""
    # TODO(M2): 404 with code COURSE_NOT_FOUND when missing.
    return {"slug": slug, "title": None, "lessons": []}


@router.post("/{course_id}/enroll")
def enroll(course_id: str, user: CurrentUser) -> dict:
    # TODO(M2): insert into enrollments, then emit("course.enrolled", {...}).
    return {"course_id": course_id, "enrolled": False}
