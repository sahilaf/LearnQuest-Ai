"""Aggregate progress and learning history.

OWNER: Member 2. See plan.md 7.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/me", tags=["progress"])


@router.get("/enrollments")
def my_enrollments(user: CurrentUser) -> dict:
    # TODO(M2): enrollments joined with course + completion percentage.
    return {"items": []}


@router.get("/progress")
def my_progress(user: CurrentUser) -> dict:
    """Per-course completion percentages for the dashboard."""
    # TODO(M2): completed lessons / total lessons per enrolled course.
    return {"items": []}


@router.get("/history")
def my_history(user: CurrentUser, page: int = 1, page_size: int = 20) -> dict:
    """Timeline of completed lessons and quiz attempts."""
    # TODO(M2): union lesson_progress and quiz_attempts ordered by date.
    return {"items": [], "total": 0, "page": page, "page_size": page_size}
