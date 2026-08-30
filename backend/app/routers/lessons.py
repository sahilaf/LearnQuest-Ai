"""Lesson content and delivery.

OWNER: Member 2. See plan.md 7.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/{lesson_id}")
def get_lesson(lesson_id: str, user: CurrentUser) -> dict:
    """Lesson markdown, video, tags and the caller's progress on it."""
    # TODO(M2): join lesson with lesson_progress for this user.
    return {"id": lesson_id, "title": None, "content_md": "", "topic_tags": []}


@router.post("/{lesson_id}/progress")
def update_progress(lesson_id: str, user: CurrentUser, payload: dict) -> dict:
    """Upsert progress. On status=completed, emit("lesson.completed", {...})."""
    # TODO(M2): upsert lesson_progress, then emit. M1 and M4 both depend on that event.
    return {"lesson_id": lesson_id, "status": payload.get("status", "in_progress")}
