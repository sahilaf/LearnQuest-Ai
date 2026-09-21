"""XP, badges, streaks, challenges, leaderboard.

OWNER: Member 4. See plan.md 9.8.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser
from app.models.gamification import Badge, UserBadge, UserStats
from app.services import badge_checker, xp_engine  # noqa: F401
from app.services.badge_checker import get_badge_progress
from app.services.xp_engine import xp_for_level

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/me/stats")
def my_stats(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict:
    """Everything the dashboard header needs."""
    user_uuid = None
    if user and "id" in user:
        try:
            user_uuid = uuid.UUID(str(user["id"]))
        except ValueError:
            user_uuid = None

    if db is not None and user_uuid:
        stats = db.query(UserStats).filter(UserStats.user_id == user_uuid).first()
        if not stats:
            try:
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
                db.commit()
                db.refresh(stats)
            except Exception:
                db.rollback()
                stats = None

        if stats:
            next_xp = xp_for_level(stats.level + 1)
            return {
                "xp": stats.xp,
                "level": stats.level,
                "next_level_xp": next_xp,
                "coins": stats.coins,
                "current_streak": stats.current_streak,
                "longest_streak": stats.longest_streak,
                "total_learning_seconds": stats.total_learning_seconds,
            }

    return {
        "xp": 0,
        "level": 1,
        "next_level_xp": xp_for_level(2),
        "coins": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "total_learning_seconds": 0,
    }


@router.get("/me/badges")
@router.get("/me/achievements")
def my_achievements(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict:
    """Earned badges plus locked ones with live progress toward requirements."""
    user_uuid = None
    if user and "id" in user:
        try:
            user_uuid = uuid.UUID(str(user["id"]))
        except ValueError:
            user_uuid = None

    if db is None or not user_uuid:
        return {
            "earned": [],
            "locked": [],
            "all": [],
            "total_earned": 0,
            "total_badges": 0,
        }

    # Query all available badges
    badges = db.query(Badge).order_by(Badge.xp_reward.asc(), Badge.name.asc()).all()

    # Query earned user_badges for this user
    user_badges = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_uuid)
        .all()
    )
    earned_map = {ub.badge_id: ub.earned_at for ub in user_badges}

    earned_list = []
    locked_list = []

    for badge in badges:
        is_earned = badge.id in earned_map
        earned_at = earned_map[badge.id].isoformat() if is_earned else None

        # Calculate progress info
        progress_info = get_badge_progress(db, user_uuid, badge)
        if is_earned:
            progress_info["percentage"] = 100
            progress_info["satisfied"] = True

        badge_data = {
            "id": str(badge.id),
            "code": badge.code,
            "name": badge.name,
            "description": badge.description,
            "icon": badge.icon or "🏆",
            "xp_reward": badge.xp_reward,
            "is_earned": is_earned,
            "earned_at": earned_at,
            "criteria": badge.criteria,
            "progress": progress_info,
        }

        if is_earned:
            earned_list.append(badge_data)
        else:
            locked_list.append(badge_data)

    return {
        "earned": earned_list,
        "locked": locked_list,
        "all": earned_list + locked_list,
        "total_earned": len(earned_list),
        "total_badges": len(badges),
    }


# Backwards compatible alias
my_badges = my_achievements


@router.get("/challenges/today")
def todays_challenges(user: CurrentUser) -> dict:
    """Three challenges for today with the caller's progress."""
    # TODO(M4): lazily generate today's set on first request of the day.
    return {"items": []}


@router.post("/challenges/{challenge_id}/claim")
def claim_challenge(challenge_id: str, user: CurrentUser) -> dict:
    # TODO(M4): verify completion server-side before awarding.
    return {"challenge_id": challenge_id, "claimed": False, "xp_awarded": 0}


@router.get("/leaderboard")
def leaderboard(
    user: CurrentUser, scope: str = "global", period: str = "weekly"
) -> dict:
    """Top 50 plus the caller's own rank, pinned even when outside the top 50.

    Weekly sums xp_events over the window - which is why every award needs an event row.
    """
    # TODO(M4): respect preferences.leaderboard_opt_out.
    return {"items": [], "me": None, "scope": scope, "period": period}


@router.get("/notifications")
def notifications(user: CurrentUser) -> dict:
    return {"items": [], "unread": 0}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, user: CurrentUser) -> dict:
    return {"id": notification_id, "is_read": True}
