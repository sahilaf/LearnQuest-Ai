"""Review queue scheduling. OWNER: Member 1. See plan.md 3.3 and 6.12.

The queue is what the app opens to. It schedules TOPICS, not stored questions - the
question is picked fresh each time, so a learner cannot memorise the item instead
of the idea.

Where the question comes from
-----------------------------
The question bank first: it is instant, free, and already vetted. A different
question from the one shown last time is preferred, so a review is not a rerun.
Only a topic with nothing in the bank is sent to the model, and at most
MAX_GENERATED_PER_LOAD of those per page load - one generation is ~8s, and a
queue of fifteen new topics would otherwise take two minutes to open.

How a topic gets in
-------------------
Every topic a learner answers a quiz question on is enrolled, via the same
`quiz.submitted` event the misconception engine listens to. New topics are due
immediately, the way a new card is in any spaced-repetition system; after that
the interval is SM-2-lite.
"""

from __future__ import annotations

import logging
import random
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("learnquest.scheduler")

MAX_DAILY_ITEMS = 15
EASE = 2.5
MAX_INTERVAL_DAYS = 60
WRONG_INTERVAL_DAYS = 2
MAX_GENERATED_PER_LOAD = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def next_interval(interval_days: int, correct: bool) -> int:
    """SM-2-lite. Defensible in a viva, and about ten lines of code.

        correct -> interval * 2.5, capped at 60 days
        wrong   -> back to 2 days
    """
    if not correct:
        return WRONG_INTERVAL_DAYS
    return max(1, min(int(max(1, interval_days) * EASE), MAX_INTERVAL_DAYS))


def interleave(items: list) -> list:
    """Order items so the same topic never appears twice in a row when avoidable.

    Round-robin across topics. Interleaving is a real learning gain for almost no
    extra code: a learner has to work out WHICH idea a question needs, rather
    than coasting on the one they just used.
    """
    groups: "OrderedDict[str, list]" = OrderedDict()
    for item in items:
        groups.setdefault(item.topic_tag, []).append(item)

    out = []
    while groups:
        for tag in list(groups):
            out.append(groups[tag].pop(0))
            if not groups[tag]:
                del groups[tag]
    return out


def enrol_topic(db, user_id, topic_tag: str, source_lesson_id=None):
    """Add a topic to the queue the first time the learner touches it.

    Idempotent: an existing item is left alone, so enrolling again never resets
    an interval the learner has earned.
    """
    from app.models.ai import ReviewItem

    uid = _as_uuid(user_id)
    if uid is None or not topic_tag:
        return None

    item = (
        db.query(ReviewItem)
        .filter(
            ReviewItem.user_id == uid,
            ReviewItem.topic_tag == topic_tag,
            ReviewItem.source_lesson_id.is_(None)
            if source_lesson_id is None
            else ReviewItem.source_lesson_id == source_lesson_id,
        )
        .first()
    )
    if item is None:
        item = ReviewItem(
            user_id=uid,
            topic_tag=topic_tag,
            source_lesson_id=source_lesson_id,
            due_at=_now(),
            interval_days=1,
            streak=0,
        )
        db.add(item)
        db.flush()
    return item


def _enrol_known_topics(db, user_id: uuid.UUID) -> None:
    """Make sure every topic with mastery history is in the queue.

    Covers learners whose history predates the queue, so it is not empty for
    exactly the people who have done the most work.
    """
    from app.models.ai import ReviewItem, TopicMastery
    from app.services.topics import active_tags

    known = set(active_tags(db))
    have = {
        row[0]
        for row in db.query(ReviewItem.topic_tag).filter(ReviewItem.user_id == user_id).all()
    }
    for (tag,) in db.query(TopicMastery.topic_tag).filter(TopicMastery.user_id == user_id).all():
        if tag in known and tag not in have:
            enrol_topic(db, user_id, tag)
            have.add(tag)


def _pick_question(db, item):
    """A bank question for this topic, preferring one not shown last time."""
    from app.models.quiz import Question

    candidates = db.query(Question).filter(Question.topic_tag == item.topic_tag).all()
    if not candidates:
        return None
    fresh = [q for q in candidates if q.id != item.question_id] or candidates
    return random.choice(fresh)


async def _generate_question(db, user_id, topic_tag: str):
    """Fallback for a topic with no bank questions: one generated question."""
    from app.models.quiz import Question
    from app.services.quiz_generator import generate_questions, persist_quiz

    questions = await generate_questions(
        db,
        lesson_content="",
        lesson_title=f"Review: {topic_tag}",
        allowed_tags=[topic_tag],
        num_questions=1,
        difficulty="medium",
        types=("mcq", "true_false", "short_answer"),
    )
    if not questions:
        return None
    quiz = persist_quiz(
        db, user_id=user_id, questions=questions, title="Review", topic_tags=[topic_tag]
    )
    return db.query(Question).filter(Question.quiz_id == quiz.id).first()


async def due_items(db, user_id, limit: int = MAX_DAILY_ITEMS) -> list[dict[str, Any]]:
    """Topics due now, interleaved, each with the question to ask."""
    from app.models.ai import ReviewItem, Topic

    uid = _as_uuid(user_id)
    if uid is None:
        return []

    _enrol_known_topics(db, uid)
    db.commit()

    due = (
        db.query(ReviewItem)
        .filter(ReviewItem.user_id == uid, ReviewItem.due_at <= _now())
        .order_by(ReviewItem.due_at.asc())
        .limit(limit * 2)  # headroom for items we cannot find a question for
        .all()
    )
    labels = {t.tag: t.label for t in db.query(Topic).all()}

    out: list[dict[str, Any]] = []
    generated = 0
    for item in interleave(due):
        if len(out) >= limit:
            break

        question = _pick_question(db, item)
        if question is None and generated < MAX_GENERATED_PER_LOAD:
            generated += 1
            try:
                question = await _generate_question(db, uid, item.topic_tag)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not generate a review question: %s", exc)
        if question is None:
            # Deferred, not dropped: it stays due and is offered next time.
            continue

        item.question_id = question.id
        out.append(
            {
                "id": str(item.id),
                "topic_tag": item.topic_tag,
                "topic_name": labels.get(item.topic_tag, item.topic_tag),
                "type": question.type,
                "prompt": question.prompt,
                "options": question.options,
                "due_at": item.due_at.isoformat() if item.due_at else None,
                "interval_days": item.interval_days,
                "streak": item.streak,
            }
        )

    db.commit()
    return out


def record_answer(db, user_id, item_id, correct: bool):
    """Update the item's interval, streak and due_at after an answer."""
    from app.models.ai import ReviewItem

    uid = _as_uuid(user_id)
    iid = _as_uuid(item_id)
    item = (
        db.query(ReviewItem)
        .filter(ReviewItem.id == iid, ReviewItem.user_id == uid)
        .first()
        if uid and iid
        else None
    )
    if item is None:
        return None

    item.interval_days = next_interval(item.interval_days or 1, correct)
    item.streak = (item.streak or 0) + 1 if correct else 0
    item.last_reviewed_at = _now()
    item.due_at = _now() + timedelta(days=item.interval_days)
    return item


# --------------------------------------------------------------------------- #
# Enrolment: every topic a learner is quizzed on joins the queue.
# --------------------------------------------------------------------------- #
from app.services.events import register_handler  # noqa: E402


@register_handler("quiz.submitted")
def _enrol_from_quiz(db, user_id, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.mastery import _load_answers_from_attempt

    answers = (payload or {}).get("answers") or []
    if not answers and (payload or {}).get("attempt_id"):
        answers = _load_answers_from_attempt(db, payload["attempt_id"])

    enrolled = 0
    for item in answers:
        tag = item.get("topic_tag") if isinstance(item, dict) else None
        if tag and enrol_topic(db, user_id, tag) is not None:
            enrolled += 1
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not commit review enrolment: %s", exc)
        db.rollback()
    return {"enrolled": enrolled}
