"""XP, levels, streaks and gamification engine.

OWNER: Member 4 (Gamification & Analytics).
REFERENCE: plan.md §9.2, §9.3, §4.3.

This module is the single business logic source of truth for:
- Awarding XP and maintaining an immutable audit ledger in `xp_events`
- Calculating levels using the exponential curve (100 * n^1.5)
- Handling streaks safely with user local dates
- Enforcing caps (such as the 25 XP daily tutor cap)
- Subscribing to application events via the Event Bus
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func

from app.models.gamification import UserStats, XPEvent
from app.services.events import register_handler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("learnquest.gamification")

# XP Award Constants (plan.md §9.2)
XP_AWARDS: dict[str, int] = {
    "lesson.completed": 50,
    "quiz.submitted_base": 10,
    "quiz.per_correct": 5,
    "quiz.perfect_bonus": 25,
    "course.enrolled": 20,
    "course.completed": 200,
    "tutor.session": 5,
    "daily.login": 10,
}

TUTOR_XP_DAILY_CAP = 25
STREAK_BONUS_PER_DAY = 5
STREAK_BONUS_MAX_DAYS = 10


def _normalize_uuid(val: Any) -> UUID:
    """Normalize a string or UUID into a valid UUID instance.

    If given an arbitrary non-UUID string (e.g., in unit tests), deterministically
    generates a UUID5 within the DNS namespace so database queries succeed.
    """
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, val)
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def xp_for_level(n: int) -> int:
    """Calculate cumulative XP threshold required to reach level n.

    Formula: 100 * (n ^ 1.5)
    Level 2 = 282 XP
    Level 5 = 1118 XP
    Level 10 = 3162 XP
    """
    if n <= 1:
        return 100
    return int(100 * (n**1.5))


def level_from_xp(xp: int) -> int:
    """Determine the user's level based on cumulative XP.

    A user begins at Level 1 with 0 XP. As XP reaches or exceeds the threshold
    for level n + 1, level increments.
    """
    if xp < 0:
        return 1
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


# Alias to maintain backwards compatibility with earlier stubs
level_for_xp = level_from_xp


def get_today_tutor_xp(
    db: Session | Any,
    user_id: UUID | str | Any,
    local_date: date | None = None,
) -> int:
    """Sum total XP earned by a user from tutor sessions today (local date)."""
    if db is None:
        return 0

    user_uuid = _normalize_uuid(user_id)
    if local_date is None:
        local_date = date.today()

    start_of_day = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)
    end_of_day = datetime.combine(local_date, datetime.max.time(), tzinfo=timezone.utc)

    total = (
        db.query(func.coalesce(func.sum(XPEvent.xp_awarded), 0))
        .filter(
            XPEvent.user_id == user_uuid,
            XPEvent.event_type == "tutor.session",
            XPEvent.created_at >= start_of_day,
            XPEvent.created_at <= end_of_day,
        )
        .scalar()
    )
    return int(total or 0)


def award_xp(
    db: Session | Any,
    user_id: UUID | str | Any,
    amount: int,
    reason: str = "",
    event_type: str | None = None,
    ref_type: str | None = None,
    ref_id: UUID | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Award XP to a user, update user_stats, and write an immutable xp_events row.

    CRITICAL RULE: Never mutate user_stats.xp without creating a corresponding
    xp_events record.

    Args:
        db: Active SQLAlchemy database session.
        user_id: ID of the recipient user.
        amount: Integer XP amount to award (must be > 0).
        reason: Human-readable description or event type fallback.
        event_type: Specific event type identifier (e.g. 'lesson.completed').
        ref_type: Optional resource category ('lesson', 'quiz', 'course', etc.).
        ref_id: Optional resource UUID for deduplication and audit linking.
        metadata: Optional dictionary with extra context.

    Returns:
        dict with: xp_awarded, total_xp, old_level, new_level, leveled_up, event_id.
    """
    # Support positional argument swapping if called as award_xp(db, user_id, event_type, amount)
    if isinstance(amount, str) and isinstance(reason, int):
        event_type, amount = amount, reason
        reason = event_type

    effective_event_type = event_type or reason or "manual"
    user_uuid = _normalize_uuid(user_id)
    ref_uuid = _normalize_uuid(ref_id) if ref_id is not None else None

    # Graceful handling for mock/unconfigured database environments
    if db is None:
        logger.warning("award_xp called with no database session; returning mock award.")
        new_level = level_from_xp(amount)
        return {
            "xp_awarded": amount,
            "total_xp": amount,
            "old_level": 1,
            "new_level": new_level,
            "leveled_up": new_level > 1,
            "event_id": None,
            "duplicate": False,
        }

    if amount <= 0:
        stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
        current_xp = stats.xp if stats else 0
        current_lvl = stats.level if stats else 1
        return {
            "xp_awarded": 0,
            "total_xp": current_xp,
            "old_level": current_lvl,
            "new_level": current_lvl,
            "leveled_up": False,
            "event_id": None,
            "duplicate": False,
        }

    try:
        # 1. Fetch or automatically create user_stats row
        stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
        if not stats:
            stats = UserStats(
                user_id=user_uuid,
                xp=0,
                level=1,
                coins=0,
                current_streak=0,
                longest_streak=0,
                total_learning_seconds=0,
            )
            db.add(stats)
            db.flush()

        # 2. Idempotency check: prevent duplicate awards for the same ref_id and event
        if ref_uuid is not None:
            existing_event = (
                db.query(XPEvent)
                .filter(
                    XPEvent.user_id == user_uuid,
                    XPEvent.event_type == effective_event_type,
                    XPEvent.ref_id == ref_uuid,
                )
                .first()
            )
            if existing_event:
                logger.info(
                    "XP already awarded for user=%s, event=%s, ref_id=%s - skipping duplicate.",
                    user_uuid,
                    effective_event_type,
                    ref_uuid,
                )
                return {
                    "xp_awarded": 0,
                    "total_xp": stats.xp,
                    "old_level": stats.level,
                    "new_level": stats.level,
                    "leveled_up": False,
                    "event_id": str(existing_event.id),
                    "duplicate": True,
                }

        # 3. Calculate new level and level-up detection
        old_xp = stats.xp
        old_level = stats.level
        new_xp = old_xp + amount
        new_level = level_from_xp(new_xp)
        leveled_up = new_level > old_level

        # 4. Mutate stats alongside creating the immutable xp_events ledger row
        stats.xp = new_xp
        stats.level = new_level

        xp_event = XPEvent(
            id=uuid.uuid4(),
            user_id=user_uuid,
            event_type=effective_event_type,
            xp_awarded=amount,
            ref_type=ref_type,
            ref_id=ref_uuid,
            created_at=datetime.now(timezone.utc),
        )
        db.add(xp_event)
        db.commit()
        db.refresh(stats)

        if leveled_up:
            logger.info(
                "User %s leveled up from L%d to L%d! Total XP: %d",
                user_uuid,
                old_level,
                new_level,
                new_xp,
            )

        return {
            "xp_awarded": amount,
            "total_xp": stats.xp,
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "event_id": str(xp_event.id),
            "duplicate": False,
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Database error during award_xp (user_id=%s, amount=%d, event=%s)",
            user_id,
            amount,
            effective_event_type,
        )
        raise


def update_streak(
    db: Session | Any,
    user_id: UUID | str | Any,
    local_date: date | str | None = None,
) -> int:
    """Update streak on learner activity using user local date.

    Rules:
        - Same day -> no change to current streak
        - Yesterday -> increment current streak (+1)
        - Broken gap (> 1 day) -> reset current streak to 1
        - Maintain longest_streak alongside
    """
    if db is None:
        return 1

    user_uuid = _normalize_uuid(user_id)

    if isinstance(local_date, str):
        try:
            local_date = date.fromisoformat(local_date)
        except ValueError:
            local_date = None

    if local_date is None and db is not None:
        try:
            from app.models.user import User
            user = db.query(User).filter(User.id == user_uuid).first()
            if user and user.preferences and "timezone" in user.preferences:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(user.preferences["timezone"])
                local_date = datetime.now(tz).date()
        except Exception:
            local_date = None

    if local_date is None:
        local_date = date.today()

    try:
        stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
        if not stats:
            stats = UserStats(
                user_id=user_uuid,
                xp=0,
                level=1,
                coins=0,
                current_streak=1,
                longest_streak=1,
                last_active_date=local_date,
                total_learning_seconds=0,
            )
            db.add(stats)
            db.commit()
            db.refresh(stats)

            # Emit streak.updated event for badge checker and other subscribers
            try:
                from app.services.events import emit
                emit(
                    db,
                    user_uuid,
                    "streak.updated",
                    {
                        "current_streak": stats.current_streak,
                        "longest_streak": stats.longest_streak,
                        "local_date": local_date.isoformat(),
                    },
                )
            except Exception:
                logger.warning("Could not emit streak.updated event for user %s", user_id)

            return stats.current_streak

        if stats.last_active_date == local_date:
            return stats.current_streak

        if stats.last_active_date == local_date - timedelta(days=1):
            stats.current_streak += 1
        else:
            stats.current_streak = 1

        stats.longest_streak = max(stats.longest_streak, stats.current_streak)
        stats.last_active_date = local_date
        db.commit()
        db.refresh(stats)

        # Emit streak.updated event for badge checker and other subscribers
        try:
            from app.services.events import emit
            emit(
                db,
                user_uuid,
                "streak.updated",
                {
                    "current_streak": stats.current_streak,
                    "longest_streak": stats.longest_streak,
                    "local_date": local_date.isoformat(),
                },
            )
        except Exception:
            logger.warning("Could not emit streak.updated event for user %s", user_id)

        return stats.current_streak

    except Exception:
        db.rollback()
        logger.exception("Failed to update streak for user %s", user_id)
        raise


# ==============================================================================
# Event Bus Handlers (Subscribed to cross-module domain events)
# ==============================================================================


@register_handler("lesson.completed")
def on_lesson_completed(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle lesson completion: award +50 XP, update learning time and streak."""
    lesson_id = payload.get("lesson_id")
    seconds = payload.get("seconds", 0)
    local_date = payload.get("local_date") or payload.get("date")

    # Update learning streak on lesson completion
    if db is not None:
        try:
            update_streak(db, user_id, local_date=local_date)
        except Exception:
            logger.exception("Could not update streak on lesson.completed for user %s", user_id)

    result = award_xp(
        db=db,
        user_id=user_id,
        amount=XP_AWARDS["lesson.completed"],
        reason="lesson.completed",
        event_type="lesson.completed",
        ref_type="lesson",
        ref_id=lesson_id,
        metadata=payload,
    )

    # If learning seconds are provided and DB is connected, increment learning time
    if db is not None and seconds:
        try:
            user_uuid = _normalize_uuid(user_id)
            stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
            if stats:
                stats.total_learning_seconds += int(seconds)
                db.commit()
                db.refresh(stats)
        except Exception:
            logger.exception("Could not update total_learning_seconds for user %s", user_id)

    return result


@register_handler("quiz.submitted")
def on_quiz_submitted(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle quiz submission: 10 base XP + (5 * correct) + (25 bonus if perfect), update streak."""
    quiz_id = payload.get("quiz_id") or payload.get("attempt_id")
    correct_count = int(payload.get("correct_count", payload.get("correct", 0)))
    total_questions = int(payload.get("total_questions", payload.get("total", 0)))
    local_date = payload.get("local_date") or payload.get("date")

    # Update streak on quiz completion
    if db is not None:
        try:
            update_streak(db, user_id, local_date=local_date)
        except Exception:
            logger.exception("Could not update streak on quiz.submitted for user %s", user_id)

    base_xp = XP_AWARDS["quiz.submitted_base"]
    correct_xp = correct_count * XP_AWARDS["quiz.per_correct"]
    is_perfect = total_questions > 0 and correct_count >= total_questions
    perfect_bonus = XP_AWARDS["quiz.perfect_bonus"] if is_perfect else 0

    total_xp = base_xp + correct_xp + perfect_bonus

    return award_xp(
        db=db,
        user_id=user_id,
        amount=total_xp,
        reason="quiz.submitted",
        event_type="quiz.submitted",
        ref_type="quiz",
        ref_id=quiz_id,
        metadata={
            **payload,
            "base_xp": base_xp,
            "correct_xp": correct_xp,
            "perfect_bonus": perfect_bonus,
            "is_perfect": is_perfect,
        },
    )


@register_handler("course.enrolled")
def on_course_enrolled(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle course enrollment: award +20 XP."""
    course_id = payload.get("course_id")
    return award_xp(
        db=db,
        user_id=user_id,
        amount=XP_AWARDS["course.enrolled"],
        reason="course.enrolled",
        event_type="course.enrolled",
        ref_type="course",
        ref_id=course_id,
        metadata=payload,
    )


@register_handler("course.completed")
def on_course_completed(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle course completion: award +200 XP, update streak."""
    course_id = payload.get("course_id")
    local_date = payload.get("local_date") or payload.get("date")

    if db is not None:
        try:
            update_streak(db, user_id, local_date=local_date)
        except Exception:
            logger.exception("Could not update streak on course.completed for user %s", user_id)

    return award_xp(
        db=db,
        user_id=user_id,
        amount=XP_AWARDS["course.completed"],
        reason="course.completed",
        event_type="course.completed",
        ref_type="course",
        ref_id=course_id,
        metadata=payload,
    )


@register_handler("tutor.session")
def on_tutor_session(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle tutor session: award +5 XP, strictly capped at 25 XP per user per day."""
    conversation_id = payload.get("conversation_id")
    base_amount = XP_AWARDS["tutor.session"]

    # Enforce daily tutor cap (max 25 XP/day)
    today_tutor_xp = get_today_tutor_xp(db, user_id)
    if today_tutor_xp >= TUTOR_XP_DAILY_CAP:
        logger.info(
            "User %s has reached the tutor daily XP cap (%d/%d XP). No XP awarded.",
            user_id,
            today_tutor_xp,
            TUTOR_XP_DAILY_CAP,
        )
        return {
            "xp_awarded": 0,
            "total_xp": 0,
            "old_level": 1,
            "new_level": 1,
            "leveled_up": False,
            "event_id": None,
            "daily_cap_reached": True,
        }

    # Grant up to the remaining allowance
    award_amount = min(base_amount, TUTOR_XP_DAILY_CAP - today_tutor_xp)

    return award_xp(
        db=db,
        user_id=user_id,
        amount=award_amount,
        reason="tutor.session",
        event_type="tutor.session",
        ref_type="conversation",
        ref_id=conversation_id,
        metadata={**payload, "today_tutor_xp_before": today_tutor_xp},
    )


@register_handler("daily.login")
def on_daily_login(
    db: Session | Any,
    user_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Handle daily login: award +10 XP and streak bonus on first login of the day."""
    user_uuid = _normalize_uuid(user_id)
    if "date" in payload and payload["date"]:
        try:
            today = date.fromisoformat(str(payload["date"]))
        except ValueError:
            today = date.today()
    else:
        today = date.today()

    # Calculate streak bonus on activity
    current_streak = update_streak(db, user_uuid, local_date=today)
    streak_bonus = STREAK_BONUS_PER_DAY * min(current_streak, STREAK_BONUS_MAX_DAYS)
    total_login_xp = XP_AWARDS["daily.login"] + streak_bonus

    # Deduplicate: check if daily.login was already awarded today
    if db is not None:
        today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        existing_today = (
            db.query(XPEvent)
            .filter(
                XPEvent.user_id == user_uuid,
                XPEvent.event_type == "daily.login",
                XPEvent.created_at >= today_start,
            )
            .first()
        )
        if existing_today:
            logger.info("Daily login XP already claimed today by user %s.", user_id)
            stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
            return {
                "xp_awarded": 0,
                "total_xp": stats.xp if stats else 0,
                "old_level": stats.level if stats else 1,
                "new_level": stats.level if stats else 1,
                "leveled_up": False,
                "event_id": str(existing_today.id),
                "duplicate": True,
            }

    return award_xp(
        db=db,
        user_id=user_id,
        amount=total_login_xp,
        reason="daily.login",
        event_type="daily.login",
        ref_type="daily_login",
        ref_id=None,
        metadata={
            **payload,
            "base_xp": XP_AWARDS["daily.login"],
            "streak_bonus": streak_bonus,
            "current_streak": current_streak,
        },
    )


def register_xp_handlers() -> None:
    """Register all XP engine handlers with the Event Bus.

    Safe to call multiple times; prevents duplicate handler registration.
    """
    from app.services.events import HANDLERS, register_handler

    handlers_map = {
        "lesson.completed": on_lesson_completed,
        "quiz.submitted": on_quiz_submitted,
        "course.enrolled": on_course_enrolled,
        "course.completed": on_course_completed,
        "tutor.session": on_tutor_session,
        "daily.login": on_daily_login,
    }
    for event_type, handler_func in handlers_map.items():
        if handler_func not in HANDLERS.get(event_type, []):
            register_handler(event_type)(handler_func)


# Ensure handlers are registered on module load
register_xp_handlers()

