"""Daily challenges service: generation, progress tracking, claiming, and event listeners.

OWNER: Member 4 (Gamification & Analytics).
REFERENCE: plan.md §9.5, §9.9.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.gamification import DailyChallenge, Notification, UserChallenge, UserStats, XPEvent
from app.services.events import emit, register_handler
from app.services.xp_engine import _utc_today, award_xp

logger = logging.getLogger("learnquest.challenges")

# Pool of daily challenge templates from which 3 are selected each day
CHALLENGE_POOL = [
    {
        "challenge_type": "lesson_complete",
        "title": "Daily Scholar",
        "description": "Complete at least 1 lesson today.",
        "target_value": 1,
        "xp_reward": 30,
        "coin_reward": 5,
    },
    {
        "challenge_type": "quiz_complete",
        "title": "Quiz Challenger",
        "description": "Complete 1 quiz to test your mastery.",
        "target_value": 1,
        "xp_reward": 30,
        "coin_reward": 5,
    },
    {
        "challenge_type": "quiz_score",
        "title": "High Scorer",
        "description": "Score 80% or higher on any quiz attempt today.",
        "target_value": 80,
        "xp_reward": 40,
        "coin_reward": 10,
    },
    {
        "challenge_type": "tutor_chat",
        "title": "Inquisitive Mind",
        "description": "Chat with Redwan or ask at least 2 questions.",
        "target_value": 2,
        "xp_reward": 25,
        "coin_reward": 5,
    },
    {
        "challenge_type": "study_time",
        "title": "Deep Focus",
        "description": "Spend at least 5 minutes (300 seconds) learning today.",
        "target_value": 300,
        "xp_reward": 35,
        "coin_reward": 5,
    },
]


def _normalize_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, val)
    return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def get_or_create_daily_challenges(
    db: Session, target_date: date | None = None
) -> list[DailyChallenge]:
    """Retrieve or generate exactly 3 daily challenges for the given date.

    Deterministic selection ensures all users on that day receive the same set.
    """
    if target_date is None:
        target_date = _utc_today()

    existing = (
        db.query(DailyChallenge)
        .filter(DailyChallenge.date == target_date)
        .order_by(DailyChallenge.id.asc())
        .all()
    )
    if len(existing) >= 3:
        return existing[:3]

    # Select 3 templates deterministically based on date ordinal
    day_seed = target_date.toordinal()
    pool_len = len(CHALLENGE_POOL)
    existing_types = {c.challenge_type for c in existing}

    created = list(existing)
    for i in range(pool_len):
        if len(created) >= 3:
            break
        idx = (day_seed + i * 2) % pool_len
        template = CHALLENGE_POOL[idx]
        if template["challenge_type"] in existing_types:
            continue

        ch = DailyChallenge(
            id=uuid.uuid4(),
            date=target_date,
            title=template["title"],
            description=template["description"],
            challenge_type=template["challenge_type"],
            target_value=template["target_value"],
            xp_reward=template["xp_reward"],
            coin_reward=template["coin_reward"],
        )
        db.add(ch)
        created.append(ch)
        existing_types.add(template["challenge_type"])

    try:
        db.commit()
        for ch in created:
            db.refresh(ch)
    except Exception:
        db.rollback()
        # Query again in case another worker concurrently created them
        created = (
            db.query(DailyChallenge)
            .filter(DailyChallenge.date == target_date)
            .order_by(DailyChallenge.id.asc())
            .all()
        )

    return created[:3]


def get_user_challenges_for_today(
    db: Session, user_id: UUID | str, target_date: date | None = None
) -> list[dict[str, Any]]:
    """Return today's 3 challenges populated with the user's progress and claim status."""
    user_uuid = _normalize_uuid(user_id)
    if target_date is None:
        target_date = _utc_today()

    challenges = get_or_create_daily_challenges(db, target_date)
    result = []

    for ch in challenges:
        uc = (
            db.query(UserChallenge)
            .filter(
                UserChallenge.user_id == user_uuid,
                UserChallenge.challenge_id == ch.id,
            )
            .first()
        )
        if not uc:
            uc = UserChallenge(
                id=uuid.uuid4(),
                user_id=user_uuid,
                challenge_id=ch.id,
                progress_value=0,
                is_completed=False,
                completed_at=None,
            )
            try:
                db.add(uc)
                db.commit()
                db.refresh(uc)
            except Exception:
                db.rollback()
                uc = (
                    db.query(UserChallenge)
                    .filter(
                        UserChallenge.user_id == user_uuid,
                        UserChallenge.challenge_id == ch.id,
                    )
                    .first()
                )

        # Check if user already claimed this challenge via XP ledger
        is_claimed = False
        claim_event = (
            db.query(XPEvent)
            .filter(
                XPEvent.user_id == user_uuid,
                XPEvent.event_type == "challenge.claimed",
                XPEvent.ref_type == "daily_challenge",
                XPEvent.ref_id == ch.id,
            )
            .first()
        )
        if claim_event:
            is_claimed = True

        progress = uc.progress_value if uc else 0
        is_completed = (uc and uc.is_completed) or (progress >= ch.target_value)

        result.append(
            {
                "id": str(ch.id),
                "date": ch.date.isoformat(),
                "title": ch.title,
                "description": ch.description,
                "challenge_type": ch.challenge_type,
                "target_value": ch.target_value,
                "xp_reward": ch.xp_reward,
                "coin_reward": ch.coin_reward,
                "progress_value": progress,
                "is_completed": bool(is_completed),
                "completed_at": uc.completed_at.isoformat() if (uc and uc.completed_at) else None,
                "is_claimed": is_claimed,
            }
        )

    return result


def update_challenge_progress(
    db: Session,
    user_id: UUID | str,
    challenge_type: str,
    increment: int = 1,
    absolute_value: int | None = None,
) -> list[UserChallenge]:
    """Update progress for active daily challenges matching challenge_type."""
    user_uuid = _normalize_uuid(user_id)
    today = _utc_today()

    active_challenges = (
        db.query(DailyChallenge)
        .filter(DailyChallenge.date == today, DailyChallenge.challenge_type == challenge_type)
        .all()
    )
    if not active_challenges:
        return []

    updated = []
    now = datetime.now(timezone.utc)

    for ch in active_challenges:
        uc = (
            db.query(UserChallenge)
            .filter(
                UserChallenge.user_id == user_uuid,
                UserChallenge.challenge_id == ch.id,
            )
            .first()
        )
        if not uc:
            uc = UserChallenge(
                id=uuid.uuid4(),
                user_id=user_uuid,
                challenge_id=ch.id,
                progress_value=0,
                is_completed=False,
            )
            db.add(uc)

        if absolute_value is not None:
            uc.progress_value = max(uc.progress_value, absolute_value)
        else:
            uc.progress_value += increment

        # Mark completed if reached target
        if uc.progress_value >= ch.target_value and not uc.is_completed:
            uc.is_completed = True
            uc.completed_at = now

            # Create in-app notification
            try:
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user_uuid,
                    type="challenge_completed",
                    title=f"Challenge Complete: {ch.title}!",
                    body=f"You completed '{ch.title}'. Claim your {ch.xp_reward} XP bonus!",
                    is_read=False,
                    created_at=now,
                )
                db.add(notif)
            except Exception:
                pass

        updated.append(uc)

    try:
        db.commit()
    except Exception:
        db.rollback()

    return updated


def claim_challenge(
    db: Session, user_id: UUID | str, challenge_id: UUID | str
) -> dict[str, Any]:
    """Claim reward for a completed daily challenge.

    Enforces server-side completion verification and idempotent anti-duplicate claiming.
    """
    user_uuid = _normalize_uuid(user_id)
    ch_uuid = _normalize_uuid(challenge_id)

    ch = db.query(DailyChallenge).filter(DailyChallenge.id == ch_uuid).first()
    if not ch:
        raise ValueError("Daily challenge not found.")

    uc = (
        db.query(UserChallenge)
        .filter(UserChallenge.user_id == user_uuid, UserChallenge.challenge_id == ch_uuid)
        .first()
    )
    if not uc or (not uc.is_completed and uc.progress_value < ch.target_value):
        raise ValueError("Challenge is not yet completed.")

    # Idempotency check: has this been claimed already?
    existing_claim = (
        db.query(XPEvent)
        .filter(
            XPEvent.user_id == user_uuid,
            XPEvent.event_type == "challenge.claimed",
            XPEvent.ref_type == "daily_challenge",
            XPEvent.ref_id == ch_uuid,
        )
        .first()
    )
    if existing_claim:
        raise ValueError("Challenge reward has already been claimed.")

    # Ensure completed flag is set
    if not uc.is_completed:
        uc.is_completed = True
        uc.completed_at = datetime.now(timezone.utc)

    # Award XP
    xp_result = award_xp(
        db=db,
        user_id=user_uuid,
        amount=ch.xp_reward,
        reason=f"Claimed daily challenge: {ch.title}",
        event_type="challenge.claimed",
        ref_type="daily_challenge",
        ref_id=ch.id,
        metadata={"challenge_title": ch.title, "challenge_type": ch.challenge_type},
    )

    # Award coins if configured
    coins_awarded = ch.coin_reward or 0
    if coins_awarded > 0:
        stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
        if stats:
            stats.coins += coins_awarded
            db.commit()

    # Emit event
    try:
        emit(
            db,
            user_uuid,
            "challenge.claimed",
            {
                "challenge_id": str(ch.id),
                "title": ch.title,
                "xp_awarded": ch.xp_reward,
                "coins_awarded": coins_awarded,
            },
        )
    except Exception:
        pass

    return {
        "challenge_id": str(ch.id),
        "claimed": True,
        "xp_awarded": ch.xp_reward,
        "coin_reward": coins_awarded,
    }


# ==============================================================================
# Event Handlers for Progress Updates
# ==============================================================================


@register_handler("lesson.completed")
def on_lesson_completed_challenges(db: Session, user_id: Any, payload: dict[str, Any]) -> None:
    try:
        update_challenge_progress(db, user_id, "lesson_complete", increment=1)
        seconds = int(payload.get("seconds", 60) or 60)
        update_challenge_progress(db, user_id, "study_time", increment=seconds)
    except Exception as e:
        logger.warning("Error updating challenge progress on lesson.completed: %s", e)


@register_handler("quiz.submitted")
def on_quiz_submitted_challenges(db: Session, user_id: Any, payload: dict[str, Any]) -> None:
    try:
        update_challenge_progress(db, user_id, "quiz_complete", increment=1)
        score = int(payload.get("score", 0) or 0)
        if score >= 80:
            update_challenge_progress(db, user_id, "quiz_score", absolute_value=score)
    except Exception as e:
        logger.warning("Error updating challenge progress on quiz.submitted: %s", e)


@register_handler("tutor.session")
def on_tutor_session_challenges(db: Session, user_id: Any, payload: dict[str, Any]) -> None:
    try:
        msgs = int(payload.get("message_count", 1) or 1)
        update_challenge_progress(db, user_id, "tutor_chat", increment=msgs)
    except Exception as e:
        logger.warning("Error updating challenge progress on tutor.session: %s", e)


def register_challenge_handlers() -> None:
    """Register all daily challenge event handlers with the Event Bus."""
    from app.services.events import HANDLERS, register_handler

    handlers_map = {
        "lesson.completed": on_lesson_completed_challenges,
        "quiz.submitted": on_quiz_submitted_challenges,
        "tutor.session": on_tutor_session_challenges,
    }
    for event_type, handler_func in handlers_map.items():
        if handler_func not in HANDLERS.get(event_type, []):
            register_handler(event_type)(handler_func)


register_challenge_handlers()
