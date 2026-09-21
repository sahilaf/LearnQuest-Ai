"""Data-driven badge checker and award engine.

OWNER: Member 4 (Gamification & Achievements).
REFERENCE: plan.md §9.4, §9.9.

Architecture:
- The badge system is completely data-driven: criteria are stored in `Badge.criteria` (JSONB).
- Badges are evaluated based on their criteria type (e.g. 'count', 'streak', 'stat')
  rather than hardcoded event conditionals.
- When events occur, `check_badges()` evaluates all unearned badges for the user.
- Newly earned badges create a `user_badges` row, write an in-app `Notification`,
  award badge bonus XP via `award_xp()`, and emit a `badge.earned` event.
- All handler executions are wrapped in isolated try/except blocks to guarantee
  that badge evaluation failures NEVER fail the caller's request.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.models.gamification import Badge, Notification, UserBadge, UserStats, XPEvent
from app.services.events import emit, register_handler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("learnquest.badges")


def _normalize_uuid(val: Any) -> UUID:
    """Normalize string or UUID to a valid UUID instance."""
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, val)
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


# ==============================================================================
# Data-driven criteria evaluators
# ==============================================================================


def evaluate_count_criteria(
    db: Session | Any,
    user_id: UUID,
    criteria: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate 'count' criteria: counts domain events in the XP ledger or entity tables.

    Example criteria:
        {"type": "count", "event": "lesson.completed", "threshold": 1}
    """
    if db is None:
        return {"current": 0, "target": 1, "percentage": 0, "satisfied": False, "unit": "count"}

    event_filter = criteria.get("event")
    threshold = int(criteria.get("threshold", 1))

    # Query xp_events for this user and event type
    query = db.query(XPEvent).filter(XPEvent.user_id == user_id)
    if event_filter:
        query = query.filter(XPEvent.event_type == event_filter)

    count = query.count()

    # If count is 0 and event is lesson.completed, also check lesson_progress completed
    if count == 0 and event_filter == "lesson.completed":
        try:
            from app.models.progress import LessonProgress
            count = db.query(LessonProgress).filter(
                LessonProgress.user_id == user_id,
                LessonProgress.status == "completed",
            ).count()
        except Exception:
            pass

    pct = min(100, int((count / threshold) * 100)) if threshold > 0 else 100
    return {
        "current": count,
        "target": threshold,
        "percentage": pct,
        "satisfied": count >= threshold,
        "unit": "completed",
    }


def evaluate_streak_criteria(
    db: Session | Any,
    user_id: UUID,
    criteria: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate 'streak' criteria against UserStats current_streak and longest_streak.

    Example criteria:
        {"type": "streak", "threshold": 7}
    """
    if db is None:
        return {"current": 0, "target": 7, "percentage": 0, "satisfied": False, "unit": "days"}

    threshold = int(criteria.get("threshold", 7))
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()

    current_val = 0
    if stats:
        current_val = max(stats.current_streak or 0, stats.longest_streak or 0)

    pct = min(100, int((current_val / threshold) * 100)) if threshold > 0 else 100
    return {
        "current": current_val,
        "target": threshold,
        "percentage": pct,
        "satisfied": current_val >= threshold,
        "unit": "days",
    }


def evaluate_stat_criteria(
    db: Session | Any,
    user_id: UUID,
    criteria: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate general stat criteria on UserStats (e.g. total XP, level, total_learning_seconds).

    Example criteria:
        {"type": "stat", "field": "level", "threshold": 5}
    """
    if db is None:
        return {"current": 0, "target": 1, "percentage": 0, "satisfied": False, "unit": "level"}

    field = criteria.get("field", "xp")
    threshold = int(criteria.get("threshold", 100))
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()

    current_val = 0
    if stats and hasattr(stats, field):
        current_val = getattr(stats, field) or 0

    pct = min(100, int((current_val / threshold) * 100)) if threshold > 0 else 100
    return {
        "current": current_val,
        "target": threshold,
        "percentage": pct,
        "satisfied": current_val >= threshold,
        "unit": field,
    }


# Registry of data-driven criteria evaluators
CRITERIA_EVALUATORS = {
    "count": evaluate_count_criteria,
    "streak": evaluate_streak_criteria,
    "stat": evaluate_stat_criteria,
}


def get_badge_progress(
    db: Session | Any,
    user_id: UUID | str,
    badge: Badge,
) -> dict[str, Any]:
    """Calculate the user's progress toward satisfying this badge's data-driven criteria.

    Returns:
        dict: {"current": int, "target": int, "percentage": int, "satisfied": bool, "unit": str}
    """
    user_uuid = _normalize_uuid(user_id)
    criteria = badge.criteria or {}
    criteria_type = criteria.get("type", "count")

    evaluator = CRITERIA_EVALUATORS.get(criteria_type, evaluate_count_criteria)
    try:
        return evaluator(db, user_uuid, criteria)
    except Exception:
        logger.exception("Failed to evaluate criteria for badge %s (user %s)", badge.code, user_id)
        return {"current": 0, "target": 1, "percentage": 0, "satisfied": False, "unit": "steps"}


# ==============================================================================
# Badge awarding logic
# ==============================================================================


def award_badge(
    db: Session | Any,
    user_id: UUID | str,
    badge_or_code: Badge | str,
) -> UserBadge | None:
    """Award a badge to a user.

    Idempotent: if the user already has this badge, returns None without creating duplicates.
    Writes UserBadge, creates in-app Notification, emits 'badge.earned', and awards bonus XP.
    """
    if db is None:
        return None

    user_uuid = _normalize_uuid(user_id)

    # Resolve Badge entity
    if isinstance(badge_or_code, Badge):
        badge = badge_or_code
    else:
        badge = db.query(Badge).filter(Badge.code == str(badge_or_code)).first()
        if not badge:
            logger.warning("Attempted to award unknown badge code %r to user %s", badge_or_code, user_id)
            return None

    # Idempotency check: prevent duplicate awards
    existing = db.query(UserBadge).filter(
        UserBadge.user_id == user_uuid,
        UserBadge.badge_id == badge.id,
    ).first()

    if existing:
        logger.debug("User %s already earned badge %s - skipping duplicate.", user_uuid, badge.code)
        return None

    now = datetime.now(timezone.utc)
    user_badge = UserBadge(
        id=uuid.uuid4(),
        user_id=user_uuid,
        badge_id=badge.id,
        earned_at=now,
    )
    db.add(user_badge)

    # Create in-app Notification
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_uuid,
        type="badge_earned",
        title=f"Badge Unlocked: {badge.name}!",
        body=badge.description or f"You earned the {badge.name} badge.",
        is_read=False,
        created_at=now,
    )
    db.add(notification)
    db.commit()
    db.refresh(user_badge)

    logger.info("Awarded badge %s (%s) to user %s!", badge.code, badge.name, user_uuid)

    # Award bonus XP if badge carries an XP reward
    if badge.xp_reward and badge.xp_reward > 0:
        try:
            from app.services.xp_engine import award_xp
            award_xp(
                db=db,
                user_id=user_uuid,
                amount=badge.xp_reward,
                reason="badge.earned",
                event_type="badge.earned",
                ref_type="badge",
                ref_id=badge.id,
                metadata={"badge_code": badge.code, "badge_name": badge.name},
            )
        except Exception:
            logger.exception("Failed to award XP for badge %s to user %s", badge.code, user_uuid)

    # Broadcast event via Event Bus
    try:
        emit(
            db,
            user_uuid,
            "badge.earned",
            {
                "badge_id": str(badge.id),
                "badge_code": badge.code,
                "badge_name": badge.name,
                "badge_icon": badge.icon,
                "badge_description": badge.description,
                "xp_reward": badge.xp_reward,
                "earned_at": now.isoformat(),
            },
        )
    except Exception:
        logger.warning("Failed to emit badge.earned event for badge %s", badge.code)

    return user_badge


def check_badges(
    db: Session | Any,
    user_id: UUID | str,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
) -> list[Badge]:
    """Check all unearned badges for the user using stored criteria and award satisfied ones.

    Execution is safe and isolated: exceptions are logged and never propagated to the caller.
    """
    if db is None:
        return []

    user_uuid = _normalize_uuid(user_id)
    awarded_badges: list[Badge] = []

    try:
        # Find all badges the user has NOT yet earned
        earned_subquery = (
            db.query(UserBadge.badge_id)
            .filter(UserBadge.user_id == user_uuid)
            .subquery()
        )
        unearned_badges = (
            db.query(Badge)
            .filter(~Badge.id.in_(earned_subquery))
            .all()
        )

        if not unearned_badges:
            return []

        for badge in unearned_badges:
            progress_info = get_badge_progress(db, user_uuid, badge)
            if progress_info.get("satisfied", False):
                awarded = award_badge(db, user_uuid, badge)
                if awarded:
                    awarded_badges.append(badge)

        return awarded_badges

    except Exception:
        logger.exception("Error checking badges for user %s on event %r", user_id, event_type)
        return []


# ==============================================================================
# Event Bus Subscriptions
# ==============================================================================


@register_handler("lesson.completed")
def on_lesson_completed_check_badges(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> list[Badge]:
    """Check badges on lesson completion (e.g. first_lesson badge)."""
    return check_badges(db, user_id, "lesson.completed", payload)


@register_handler("streak.updated")
def on_streak_updated_check_badges(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> list[Badge]:
    """Check badges on streak update (e.g. streak_7 badge)."""
    return check_badges(db, user_id, "streak.updated", payload)


@register_handler("quiz.submitted")
def on_quiz_submitted_check_badges(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> list[Badge]:
    """Check badges on quiz submission."""
    return check_badges(db, user_id, "quiz.submitted", payload)


@register_handler("course.completed")
def on_course_completed_check_badges(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> list[Badge]:
    """Check badges on course completion."""
    return check_badges(db, user_id, "course.completed", payload)


def register_badge_handlers() -> None:
    """Register all badge checker event handlers with the Event Bus.

    Safe to call multiple times; duplicates are automatically prevented.
    """
    from app.services.events import HANDLERS, register_handler

    handlers_map = {
        "lesson.completed": on_lesson_completed_check_badges,
        "streak.updated": on_streak_updated_check_badges,
        "quiz.submitted": on_quiz_submitted_check_badges,
        "course.completed": on_course_completed_check_badges,
    }
    for event_type, handler_func in handlers_map.items():
        if handler_func not in HANDLERS.get(event_type, []):
            register_handler(event_type)(handler_func)


# Ensure badge handlers are registered on module load
register_badge_handlers()
