"""Admin panel: users, courses, uploads.

OWNER: Member 3. See plan.md 8.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import AdminUser

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(admin: AdminUser) -> dict:
    """Counts for the admin landing page. M4 renders the charts on top of this."""
    # TODO(M3): real counts from the DB.
    return {"users": 0, "courses": 0, "enrollments": 0, "active_today": 0}


@router.get("/users")
def list_users(admin: AdminUser, page: int = 1, page_size: int = 20) -> dict:
    # TODO(M3): search + role filter + pagination.
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.post("/courses")
def create_course(admin: AdminUser, payload: dict) -> dict:
    # TODO(M3): create the course, slugify the title.
    return {"id": None, "created": False}


@router.post("/courses/{course_id}/lessons")
def create_lesson(admin: AdminUser, course_id: str, payload: dict) -> dict:
    """A lesson MUST have at least one topic_tag - M1's recommender is blind without it."""
    # TODO(M3): reject with 422 when topic_tags is empty. See plan.md 3.1.
    return {"id": None, "course_id": course_id, "created": False}
