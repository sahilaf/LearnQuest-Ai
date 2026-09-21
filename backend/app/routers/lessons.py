"""Lesson content and delivery.

OWNER: Member 2. See plan.md §7.3.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import database_is_configured, get_db
from app.deps import CurrentUser
from app.models.course import Course, Enrollment, Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Quiz
from app.services.events import emit

logger = logging.getLogger("learnquest.lessons")

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/{lesson_id}", response_model=dict[str, Any])
def get_lesson(
    lesson_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Lesson markdown, video, tags and sibling navigation."""
    if not db or not database_is_configured():
        return {
            "id": lesson_id,
            "title": "Demo Lesson",
            "content_md": "# Demo Lesson\n\nDatabase not connected.",
            "topic_tags": [],
            "estimated_minutes": 10,
            "order_index": 1,
        }

    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid lesson ID.",
        ) from err

    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.course).joinedload(Course.lessons))
        .filter(Lesson.id == l_uuid)
        .first()
    )

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lesson '{lesson_id}' not found.",
        )

    data = lesson.to_dict()

    # Member 2: attach associated practice quiz if present
    associated_quiz = (
        db.query(Quiz)
        .filter(Quiz.lesson_id == l_uuid)
        .order_by(Quiz.created_at.desc())
        .first()
    )
    data["quiz_id"] = str(associated_quiz.id) if associated_quiz else None

    # Member 2: attach user progress if authenticated
    data["progress"] = None
    data["status"] = "not_started"
    data["seconds_spent"] = 0
    data["last_position"] = 0
    data["completed_at"] = None

    if db and database_is_configured() and user and "id" in user:
        try:
            u_uuid = uuid.UUID(str(user["id"]))
            lp = (
                db.query(LessonProgress)
                .filter(LessonProgress.user_id == u_uuid, LessonProgress.lesson_id == l_uuid)
                .first()
            )
            if lp:
                data["progress"] = lp.to_dict()
                data["status"] = lp.status
                data["seconds_spent"] = lp.seconds_spent
                data["last_position"] = lp.last_position
                data["completed_at"] = lp.completed_at.isoformat() if lp.completed_at else None
        except Exception as e:
            logger.warning("Error fetching lesson progress: %s", e)

    if lesson.course:
        sorted_lessons = sorted(lesson.course.lessons, key=lambda l: l.order_index)
        data["course"] = {
            "id": str(lesson.course.id),
            "title": lesson.course.title,
            "slug": lesson.course.slug,
            "lessons": [
                {
                    "id": str(l.id),
                    "title": l.title,
                    "order_index": l.order_index,
                    "estimated_minutes": l.estimated_minutes,
                }
                for l in sorted_lessons
            ],
        }

        # Calculate previous and next lesson
        idx = next((i for i, l in enumerate(sorted_lessons) if l.id == lesson.id), -1)
        data["prev_lesson"] = (
            {"id": str(sorted_lessons[idx - 1].id), "title": sorted_lessons[idx - 1].title}
            if idx > 0
            else None
        )
        data["next_lesson"] = (
            {"id": str(sorted_lessons[idx + 1].id), "title": sorted_lessons[idx + 1].title}
            if idx >= 0 and idx < len(sorted_lessons) - 1
            else None
        )

    return data


@router.post("/{lesson_id}/progress", response_model=dict[str, Any])
def update_progress(
    lesson_id: str,
    user: CurrentUser,
    payload: dict,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Record progress heartbeat or completion. On status=completed, emits lesson.completed."""
    status_val = payload.get("status", "in_progress")
    seconds_spent = payload.get("seconds_spent", 0)
    last_position = payload.get("last_position", 0)

    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid lesson ID.",
        ) from err

    result = {
        "lesson_id": lesson_id,
        "status": status_val,
        "seconds_spent": seconds_spent,
        "last_position": last_position,
        "completed_at": None,
    }

    if db and database_is_configured() and user and "id" in user:
        try:
            u_id = uuid.UUID(str(user["id"]))
            lp = (
                db.query(LessonProgress)
                .filter(LessonProgress.user_id == u_id, LessonProgress.lesson_id == l_uuid)
                .first()
            )
            was_completed = lp.status == "completed" if lp else False

            if not lp:
                lp = LessonProgress(
                    user_id=u_id,
                    lesson_id=l_uuid,
                    status=status_val,
                    seconds_spent=seconds_spent,
                    last_position=last_position,
                )
                if status_val == "completed":
                    lp.completed_at = datetime.now(timezone.utc)
                db.add(lp)
            else:
                if status_val == "completed":
                    lp.status = "completed"
                    if not lp.completed_at:
                        lp.completed_at = datetime.now(timezone.utc)
                elif lp.status != "completed":
                    lp.status = status_val

                lp.seconds_spent = max(lp.seconds_spent, seconds_spent)
                lp.last_position = last_position

            db.commit()
            db.refresh(lp)

            result = lp.to_dict()

            # Emit event when newly completed
            if status_val == "completed" and not was_completed:
                lesson = db.query(Lesson).filter(Lesson.id == l_uuid).first()
                course_id = str(lesson.course_id) if lesson else None
                try:
                    emit(
                        db,
                        u_id,
                        "lesson.completed",
                        {
                            "lesson_id": str(l_uuid),
                            "course_id": course_id,
                            "seconds": lp.seconds_spent,
                        },
                    )
                except Exception as e:
                    logger.warning("Error emitting lesson.completed event: %s", e)

                # Check if all lessons in course are completed
                if lesson and lesson.course_id:
                    total_lessons = db.query(Lesson).filter(Lesson.course_id == lesson.course_id).count()
                    completed_lessons = (
                        db.query(LessonProgress)
                        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
                        .filter(
                            Lesson.course_id == lesson.course_id,
                            LessonProgress.user_id == u_id,
                            LessonProgress.status == "completed",
                        )
                        .count()
                    )
                    if total_lessons > 0 and completed_lessons >= total_lessons:
                        enr = (
                            db.query(Enrollment)
                            .filter(Enrollment.user_id == u_id, Enrollment.course_id == lesson.course_id)
                            .first()
                        )
                        if enr and not enr.completed_at:
                            enr.completed_at = datetime.now(timezone.utc)
                            db.commit()

        except Exception as e:
            logger.warning("Error updating lesson progress: %s", e)
            if db:
                db.rollback()

    return result
