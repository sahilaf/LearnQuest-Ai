"""Aggregate progress and learning history.

OWNER: Member 2. See plan.md §7.3.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import database_is_configured, get_db
from app.deps import CurrentUser
from app.models.course import Course, Enrollment, Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Quiz, QuizAttempt

logger = logging.getLogger("learnquest.progress")

router = APIRouter(prefix="/api/me", tags=["progress"])


def _progress_by_lesson(db: Session, user_uuid: uuid.UUID) -> dict[uuid.UUID, str]:
    """Every lesson this user has touched, mapped to its status.

    One query, whatever they are enrolled in. The endpoints below used to run a
    LessonProgress query per enrolled course inside their loop, which is an N+1:
    measured 2026-09-22, ten enrolled courses meant eleven round trips, and a
    round trip to Supabase's pooler costs ~75 ms - roughly 825 ms of pure
    network for one endpoint.

    Fetching the user's whole progress set is cheaper than an `IN` over every
    lesson id: the row count is bounded by lessons they have actually started,
    not by the size of the catalogue, and it avoids sending a huge id list.
    Only the two columns that are needed are selected.
    """
    rows = (
        db.query(LessonProgress.lesson_id, LessonProgress.status)
        .filter(LessonProgress.user_id == user_uuid)
        .all()
    )
    return {lesson_id: status for lesson_id, status in rows}


@router.get("/enrollments", response_model=dict[str, Any])
def my_enrollments(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Enrollments joined with course + completion percentage and next lesson."""
    if db is None or not user or "id" not in user:
        return {"items": [], "total": 0}

    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        return {"items": [], "total": 0}

    try:
        enrollments = (
            db.query(Enrollment)
            .options(joinedload(Enrollment.course).joinedload(Course.lessons))
            .filter(Enrollment.user_id == user_uuid)
            .order_by(Enrollment.enrolled_at.desc())
            .all()
        )

        progress_by_lesson = _progress_by_lesson(db, user_uuid)

        items: list[dict[str, Any]] = []
        for enr in enrollments:
            course = enr.course
            if not course:
                continue

            lessons = sorted(course.lessons, key=lambda l: l.order_index)
            total_lessons = len(lessons)
            lesson_ids = [l.id for l in lessons]

            completed_set = {
                lesson_id
                for lesson_id in lesson_ids
                if progress_by_lesson.get(lesson_id) == "completed"
            }

            completed_count = len(completed_set)
            percentage = (
                round((completed_count / total_lessons * 100.0), 1)
                if total_lessons > 0
                else 0.0
            )

            # Next unfinished lesson in sequence
            next_lesson = next((l for l in lessons if l.id not in completed_set), None)
            if not next_lesson and lessons:
                next_lesson = lessons[-1]

            items.append({
                "id": str(enr.id),
                "course_id": str(course.id),
                "enrolled_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
                "completed_at": enr.completed_at.isoformat() if enr.completed_at else None,
                "course": {
                    "id": str(course.id),
                    "title": course.title,
                    "slug": course.slug,
                    "description": course.description,
                    "subject": course.subject,
                    "difficulty": course.difficulty,
                    "thumbnail_url": course.thumbnail_url,
                    "estimated_hours": course.estimated_hours,
                    "total_lessons": total_lessons,
                },
                "completed_lessons": completed_count,
                "total_lessons": total_lessons,
                "completion_percentage": percentage,
                "next_lesson_id": str(next_lesson.id) if next_lesson else None,
                "next_lesson_title": next_lesson.title if next_lesson else None,
            })

        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.warning("Error fetching user enrollments: %s", e)
        return {"items": [], "total": 0}


@router.get("/progress", response_model=dict[str, Any])
def my_progress(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Per-course completion percentages, completed IDs and active lesson for the dashboard."""
    if db is None or not user or "id" not in user:
        return {"items": []}

    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        return {"items": []}

    try:
        enrollments = (
            db.query(Enrollment)
            .options(joinedload(Enrollment.course).joinedload(Course.lessons))
            .filter(Enrollment.user_id == user_uuid)
            .order_by(Enrollment.enrolled_at.desc())
            .all()
        )

        progress_by_lesson = _progress_by_lesson(db, user_uuid)

        items: list[dict[str, Any]] = []
        for enr in enrollments:
            course = enr.course
            if not course:
                continue

            lessons = sorted(course.lessons, key=lambda l: l.order_index)
            total_lessons = len(lessons)
            lesson_ids = [l.id for l in lessons]

            # Built from `lesson_ids`, so both lists come out in lesson order
            # rather than in whatever order the database returned rows.
            completed_ids = [
                str(lesson_id)
                for lesson_id in lesson_ids
                if progress_by_lesson.get(lesson_id) == "completed"
            ]
            in_progress_ids = [
                str(lesson_id)
                for lesson_id in lesson_ids
                if progress_by_lesson.get(lesson_id) == "in_progress"
            ]

            completed_set = set(completed_ids)
            completed_count = len(completed_set)
            percentage = (
                round((completed_count / total_lessons * 100.0), 1)
                if total_lessons > 0
                else 0.0
            )

            next_lesson = next((l for l in lessons if str(l.id) not in completed_set), None)
            if not next_lesson and lessons:
                next_lesson = lessons[-1]

            items.append({
                "course_id": str(course.id),
                "course_title": course.title,
                "course_slug": course.slug,
                "subject": course.subject,
                "difficulty": course.difficulty,
                "completed_lessons": completed_count,
                "total_lessons": total_lessons,
                "completion_percentage": percentage,
                "completed_lesson_ids": completed_ids,
                "in_progress_lesson_ids": in_progress_ids,
                "next_lesson_id": str(next_lesson.id) if next_lesson else None,
                "next_lesson_title": next_lesson.title if next_lesson else None,
                "enrolled_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
                "completed_at": enr.completed_at.isoformat() if enr.completed_at else None,
            })

        return {"items": items}
    except Exception as e:
        logger.warning("Error fetching course progress: %s", e)
        return {"items": []}


@router.get("/history", response_model=dict[str, Any])
def my_history(
    user: CurrentUser,
    item_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Timeline of completed lessons and quiz attempts ordered chronologically."""
    if db is None or not user or "id" not in user:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    try:
        history_items: list[dict[str, Any]] = []

        # 1. Lesson Progress items
        if not item_type or item_type == "lesson":
            lps = (
                db.query(LessonProgress)
                .options(joinedload(LessonProgress.lesson).joinedload(Lesson.course))
                .filter(
                    LessonProgress.user_id == user_uuid,
                    LessonProgress.status.in_(["completed", "in_progress"]),
                )
                .all()
            )
            for lp in lps:
                if not lp.lesson:
                    continue
                dt = lp.completed_at or datetime.now(timezone.utc)
                history_items.append({
                    "id": str(lp.id),
                    "item_type": "lesson",
                    "title": lp.lesson.title,
                    "course_id": str(lp.lesson.course_id) if lp.lesson.course_id else None,
                    "course_title": lp.lesson.course.title if lp.lesson.course else None,
                    "lesson_id": str(lp.lesson_id),
                    "quiz_id": None,
                    "attempt_id": None,
                    "status": lp.status,
                    "score": None,
                    "passed": True if lp.status == "completed" else None,
                    "seconds_spent": lp.seconds_spent,
                    "completed_at": dt,
                })

        # 2. Quiz Attempts
        if not item_type or item_type == "quiz":
            attempts = (
                db.query(QuizAttempt)
                .options(joinedload(QuizAttempt.quiz).joinedload(Quiz.lesson).joinedload(Lesson.course))
                .filter(QuizAttempt.user_id == user_uuid)
                .all()
            )
            for att in attempts:
                if not att.quiz:
                    continue
                quiz = att.quiz
                lesson = quiz.lesson
                course = lesson.course if lesson else None
                dt = att.submitted_at or att.started_at or datetime.now(timezone.utc)
                is_passed = (float(att.score) >= 70.0) if (att.score is not None and att.submitted_at) else False
                status_str = "passed" if is_passed else ("completed" if att.submitted_at else "in_progress")
                history_items.append({
                    "id": str(att.id),
                    "item_type": "quiz",
                    "title": quiz.title,
                    "quiz_id": str(quiz.id),
                    "attempt_id": str(att.id),
                    "course_id": str(course.id) if course else None,
                    "course_title": course.title if course else None,
                    "lesson_id": str(quiz.lesson_id) if quiz.lesson_id else None,
                    "status": status_str,
                    "score": round(float(att.score), 1) if att.score is not None else None,
                    "passed": is_passed if att.submitted_at else None,
                    "seconds_spent": att.duration_seconds,
                    "completed_at": dt,
                })

        # Sort all items descending by completed_at
        def _get_sort_dt(x: dict[str, Any]) -> datetime:
            val = x["completed_at"]
            if isinstance(val, datetime):
                return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
            return datetime.now(timezone.utc)

        history_items.sort(key=_get_sort_dt, reverse=True)

        total_count = len(history_items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_items = history_items[start_idx:end_idx]

        # Convert datetimes to ISO string for JSON serialization
        formatted_items: list[dict[str, Any]] = []
        for item in paged_items:
            formatted = dict(item)
            dt_val = formatted["completed_at"]
            if isinstance(dt_val, datetime):
                formatted["completed_at"] = dt_val.isoformat()
            formatted_items.append(formatted)

        return {
            "items": formatted_items,
            "total": total_count,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.warning("Error fetching learning history: %s", e)
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
