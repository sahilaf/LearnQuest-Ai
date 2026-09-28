"""Personalized recommendations. OWNER: Member 1. See plan.md 6.5.

Every recommendation carries a reason a student can read and check - "Your
mastery of SQL joins is 30%", not "Recommended for you". A recommendation with
no reason is an ad; the reason is what makes it trustworthy, and what sells it.

Scoring is a weighted sum of four signals, each in 0..1:

  weakness      1 - mastery of the lesson's topics
  prerequisite  it is the next unstarted lesson in a course they are taking
  recency       they have not touched the topic in a while
  popularity    how often other learners finish it

The reason is taken from whichever signal contributed most, so it explains the
actual ranking rather than decorating it. A live misconception outranks every
other reason: the app named a false belief, and a lesson on that topic is the
most useful thing it can suggest.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("learnquest.recommender")

WEIGHTS = {
    "weakness": 0.45,      # 1 - mastery of the lesson's topics
    "prerequisite": 0.25,  # next unstarted lesson in an enrolled course
    "recency": 0.20,       # topic not practiced in N days
    "popularity": 0.10,    # completion rate across all users
}

CACHE_TTL_SECONDS = 3600
STALE_AFTER_DAYS = 7
DEFAULT_MASTERY = 0.5
REVIEW_ITEM_MINUTES = 2
QUIZ_MINUTES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _candidates(db, user_id: uuid.UUID):
    """Lessons this learner could take next: visible to them and not finished."""
    from sqlalchemy import or_

    from app.models.course import Course, Lesson
    from app.models.progress import LessonProgress

    done = {
        row[0]
        for row in db.query(LessonProgress.lesson_id)
        .filter(LessonProgress.user_id == user_id, LessonProgress.status == "completed")
        .all()
    }
    lessons = (
        db.query(Lesson, Course)
        .join(Course, Course.id == Lesson.course_id)
        .filter(
            Course.is_published.is_(True),
            # Another learner's generated course is private to them.
            or_(Course.is_private.is_(False), Course.created_by == user_id),
        )
        .all()
    )
    return [(lesson, course) for lesson, course in lessons if lesson.id not in done]


def _next_in_enrolled(db, user_id: uuid.UUID) -> set:
    """The first unfinished lesson in each course the learner is enrolled in."""
    from app.models.course import Enrollment, Lesson
    from app.models.progress import LessonProgress

    done = {
        row[0]
        for row in db.query(LessonProgress.lesson_id)
        .filter(LessonProgress.user_id == user_id, LessonProgress.status == "completed")
        .all()
    }
    course_ids = [
        row[0]
        for row in db.query(Enrollment.course_id).filter(Enrollment.user_id == user_id).all()
    ]
    if not course_ids:
        return set()

    nxt = set()
    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id.in_(course_ids))
        .order_by(Lesson.course_id, Lesson.order_index)
        .all()
    )
    seen_courses = set()
    for lesson in lessons:
        if lesson.course_id in seen_courses or lesson.id in done:
            continue
        nxt.add(lesson.id)
        seen_courses.add(lesson.course_id)
    return nxt


def _popularity(db) -> dict:
    """Completion rate per lesson across all learners, in one grouped query."""
    from sqlalchemy import Integer, func

    from app.models.progress import LessonProgress

    rows = (
        db.query(
            LessonProgress.lesson_id,
            func.count(LessonProgress.id),
            func.sum(func.cast(LessonProgress.status == "completed", Integer)),
        )
        .group_by(LessonProgress.lesson_id)
        .all()
    )
    return {lid: (int(done or 0) / total) if total else 0.0 for lid, total, done in rows}


def score_lessons(db, user_id) -> list[dict[str, Any]]:
    """Rank every candidate lesson and attach the reason that drove its rank."""
    from app.models.ai import Topic, TopicMastery
    from app.services.mastery import misconception_status

    uid = _as_uuid(user_id)
    if uid is None:
        return []

    mastery_rows = db.query(TopicMastery).filter(TopicMastery.user_id == uid).all()
    mastery = {r.topic_tag: r for r in mastery_rows}
    labels = {t.tag: t.label for t in db.query(Topic).all()}
    next_ids = _next_in_enrolled(db, uid)
    popular = _popularity(db)
    now = _now()

    ranked = []
    for lesson, course in _candidates(db, uid):
        tags = list(lesson.topic_tags or [])
        rows = [mastery[t] for t in tags if t in mastery]

        avg_mastery = (
            sum(float(r.mastery_score or DEFAULT_MASTERY) for r in rows) / len(rows)
            if rows else DEFAULT_MASTERY
        )
        weakness = 1.0 - avg_mastery

        last_seen = max((_aware(r.last_practiced_at) for r in rows if r.last_practiced_at), default=None)
        days_idle = (now - last_seen).days if last_seen else None
        recency = 1.0 if days_idle is None else min(1.0, days_idle / (STALE_AFTER_DAYS * 2))

        prerequisite = 1.0 if lesson.id in next_ids else 0.0
        popularity = popular.get(lesson.id, 0.0)

        parts = {
            "weakness": WEIGHTS["weakness"] * weakness,
            "prerequisite": WEIGHTS["prerequisite"] * prerequisite,
            "recency": WEIGHTS["recency"] * recency,
            "popularity": WEIGHTS["popularity"] * popularity,
        }
        score = sum(parts.values())

        live = next(
            (r for r in rows if r.misconception and misconception_status(r) in ("active", "fading")),
            None,
        )
        topic = labels.get(tags[0], tags[0]) if tags else "this topic"

        # The reason comes from what actually ranked it, with the real number.
        if live is not None:
            score += 0.5  # a named false belief outranks everything
            reason = f"You believe something about {topic} that isn't quite right - this lesson addresses it."
        else:
            driver = max(parts, key=parts.get)
            if driver == "weakness" and rows:
                reason = f"Your mastery of {topic} is {round(avg_mastery * 100)}%."
            elif driver == "prerequisite":
                reason = f"It's the next lesson in {course.title}."
            elif driver == "recency" and days_idle is not None:
                reason = f"You haven't practised {topic} in {days_idle} days."
            elif driver == "popularity" and popularity > 0:
                reason = f"{round(popularity * 100)}% of learners who start it finish it."
            elif prerequisite:
                reason = f"It's the next lesson in {course.title}."
            else:
                reason = f"You haven't started {topic} yet."

        ranked.append(
            {
                "kind": "lesson",
                "target_id": str(lesson.id),
                "title": lesson.title,
                "course_title": course.title,
                "course_slug": course.slug,
                "topic_tag": tags[0] if tags else None,
                "reason": reason,
                "score": round(score, 3),
                "minutes": int(lesson.estimated_minutes or 10),
                "link": f"/lessons/{lesson.id}",
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


def recommend(db, user_id, limit: int = 5) -> list[dict]:
    """Ranked recommendations, cached for an hour, dismissed ones excluded."""
    from app.models.ai import Recommendation

    uid = _as_uuid(user_id)
    if uid is None:
        return []

    now = _now()
    cached = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == uid,
            Recommendation.is_dismissed.is_(False),
            Recommendation.expires_at > now,
        )
        .order_by(Recommendation.score.desc())
        .all()
    )
    dismissed = {
        row[0]
        for row in db.query(Recommendation.target_id)
        .filter(Recommendation.user_id == uid, Recommendation.is_dismissed.is_(True))
        .all()
    }

    if cached:
        fresh = {str(r.target_id): r for r in cached}
        # Titles and links are not cached, so rebuild them against current data.
        by_id = {r["target_id"]: r for r in score_lessons(db, uid)}
        out = []
        for target, row in fresh.items():
            if target in by_id:
                item = dict(by_id[target])
                item["id"] = str(row.id)
                item["reason"] = row.reason
                out.append(item)
        if out:
            return out[:limit]

    ranked = [r for r in score_lessons(db, uid) if _as_uuid(r["target_id"]) not in dismissed][:limit]

    # Replace the cache rather than accumulate it.
    db.query(Recommendation).filter(
        Recommendation.user_id == uid, Recommendation.is_dismissed.is_(False)
    ).delete(synchronize_session=False)
    for item in ranked:
        row = Recommendation(
            user_id=uid,
            kind=item["kind"],
            target_id=uuid.UUID(item["target_id"]),
            reason=item["reason"],
            # Numeric(4,3) holds up to 9.999; capping lower would flatten the
            # ranking so misconception-boosted items tied with everything else.
            score=min(9.999, item["score"]),
            expires_at=now + timedelta(seconds=CACHE_TTL_SECONDS),
        )
        db.add(row)
        db.flush()
        item["id"] = str(row.id)
    db.commit()
    return ranked


def dismiss(db, user_id, recommendation_id) -> bool:
    from app.models.ai import Recommendation

    uid, rid = _as_uuid(user_id), _as_uuid(recommendation_id)
    if uid is None or rid is None:
        return False
    row = (
        db.query(Recommendation)
        .filter(Recommendation.id == rid, Recommendation.user_id == uid)
        .first()
    )
    if row is None:
        return False
    row.is_dismissed = True
    db.commit()
    return True


def daily_plan(db, user_id, minutes: int = 30) -> dict:
    """Fill a time budget: due reviews first, then lessons, then one quiz.

    Reviews go first because they are the cheapest way to keep what was already
    learned, and skipping them is how forgetting starts.
    """
    from app.models.ai import ReviewItem

    uid = _as_uuid(user_id)
    budget = max(5, min(240, int(minutes or 30)))
    if uid is None:
        return {"minutes": budget, "planned_minutes": 0, "items": []}

    items: list[dict[str, Any]] = []
    used = 0

    due = (
        db.query(ReviewItem)
        .filter(ReviewItem.user_id == uid, ReviewItem.due_at <= _now())
        .count()
    )
    if due:
        take = min(due, max(1, (budget // 3) // REVIEW_ITEM_MINUTES))
        cost = take * REVIEW_ITEM_MINUTES
        items.append(
            {
                "kind": "revision",
                "title": f"Review {take} topic{'s' if take != 1 else ''}",
                "reason": f"{due} topic{'s are' if due != 1 else ' is'} due for review - "
                          "spaced review is what makes learning stick.",
                "minutes": cost,
                "link": "/review",
            }
        )
        used += cost

    for rec in recommend(db, uid, limit=8):
        if used + rec["minutes"] > budget - QUIZ_MINUTES:
            continue
        items.append(
            {
                "kind": "lesson",
                "title": rec["title"],
                "reason": rec["reason"],
                "minutes": rec["minutes"],
                "link": rec["link"],
                "target_id": rec["target_id"],
            }
        )
        used += rec["minutes"]

    if used + QUIZ_MINUTES <= budget:
        items.append(
            {
                "kind": "quiz",
                "title": "Practice your weak spots",
                "reason": "A short quiz aimed at the topics you find hardest.",
                "minutes": QUIZ_MINUTES,
                "link": "/dashboard",
            }
        )
        used += QUIZ_MINUTES

    return {"minutes": budget, "planned_minutes": used, "items": items}
