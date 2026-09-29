"""Spaced-repetition review queue. OWNER: Member 1. See services/scheduler.py.

Shapes match `frontend/src/api/review.js`, so ReviewScreen works unchanged.

A review answer is the best evidence the learner model gets. It is spaced (so it
tests memory, not the last five minutes), interleaved (so it tests recognising
WHICH idea applies), and often typed (so a wrong answer says why, not just
which). It therefore feeds everything: the schedule, mastery, the decay of an
existing misconception on a right answer, and the capture of a new one on a
wrong one.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser

# Imported for its side effect, and at module load on purpose: scheduler
# registers the quiz.submitted handler that enrols topics into this queue. A
# lazy import would leave that handler unregistered until someone first opened
# the Review page - and every quiz taken before then would enrol nothing, with
# no error anywhere. The same silent failure G1 was.
from app.services import scheduler  # noqa: F401

logger = logging.getLogger("learnquest.review")

router = APIRouter(prefix="/api/review", tags=["review"])


class AnswerRequest(BaseModel):
    answer: str = Field(default="", max_length=2000)


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return db


def _user_uuid(user: Any) -> uuid.UUID:
    try:
        return uuid.UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user.") from err


@router.get("/today")
async def today(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict[str, Any]:
    """What is due now, interleaved so the same topic never repeats back to back."""
    from app.models.ai import ReviewItem
    from app.services.scheduler import due_items

    database = _require_db(db)
    user_uuid = _user_uuid(user)
    items = await due_items(database, user_uuid)

    # The next one still to come. Without the > now filter this returned the
    # oldest *overdue* item, so an empty queue announced a review "due"
    # yesterday.
    upcoming = (
        database.query(ReviewItem.due_at)
        .filter(
            ReviewItem.user_id == user_uuid,
            ReviewItem.due_at > datetime.now(timezone.utc),
        )
        .order_by(ReviewItem.due_at.asc())
        .first()
    )
    return {
        "items": items,
        "total_due": len(items),
        # So an empty queue can say when the next review is, rather than just
        # looking broken.
        "next_due_at": upcoming[0].isoformat() if upcoming and upcoming[0] else None,
    }


@router.post("/{item_id}/answer")
async def answer(
    item_id: str,
    body: AnswerRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Grade, reschedule, and update mastery and misconceptions."""
    from app.models.ai import ReviewItem
    from app.models.quiz import Question
    from app.services.mastery import (
        capture_misconception,
        register_correct_answer,
        update_mastery,
    )
    from app.services.open_grader import grade_choice, grade_open
    from app.services.scheduler import record_answer

    database = _require_db(db)
    user_uuid = _user_uuid(user)

    try:
        iid = uuid.UUID(item_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found.") from err

    item = (
        database.query(ReviewItem)
        .filter(ReviewItem.id == iid, ReviewItem.user_id == user_uuid)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found.")

    question = (
        database.query(Question).filter(Question.id == item.question_id).first()
        if item.question_id
        else None
    )
    if question is None:
        # The item was never shown with a question - reload today's queue.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This review has no question yet. Reload your review queue.",
        )

    if question.type in ("mcq", "true_false"):
        grade = grade_choice(body.answer, question.correct_answer)
    else:
        grade = await grade_open(question.prompt, question.correct_answer, body.answer)

    misconception = None

    if grade["needs_review"]:
        # Our failure to grade, not the learner's wrong answer: the schedule is
        # left alone rather than punishing them for it.
        next_due = item.due_at
    else:
        correct = grade["is_correct"]
        record_answer(database, user_uuid, item.id, correct)
        next_due = item.due_at

        try:
            update_mastery(database, user_uuid, item.topic_tag, 1 if correct else 0, 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not update mastery from review: %s", exc)

        if correct:
            try:
                register_correct_answer(database, user_uuid, item.topic_tag)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not decay misconception: %s", exc)
        elif body.answer.strip():
            # A typed wrong answer is the richest input the misconception
            # engine gets. It still abstains when it cannot name a belief.
            try:
                misconception = await capture_misconception(
                    database,
                    user_uuid,
                    item.topic_tag,
                    {"prompt": question.prompt, "correct_answer": question.correct_answer},
                    body.answer,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not capture misconception from review: %s", exc)

    database.commit()

    return {
        "item_id": str(item.id),
        "is_correct": grade["is_correct"],
        "score_0_1": grade["score_0_1"],
        "verdict": grade["verdict"],
        "feedback": grade["feedback"],
        "needs_review": grade["needs_review"],
        "misconception": misconception,
        "next_due_at": next_due.isoformat() if next_due else None,
        "interval_days": item.interval_days,
        # Shown only once answered - reviews are practice, not an exam.
        "correct_answer": question.correct_answer,
    }
