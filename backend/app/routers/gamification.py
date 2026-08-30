"""XP, badges, streaks, challenges, leaderboard.

OWNER: Member 4. See plan.md 9.8.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/me/stats")
def my_stats(user: CurrentUser) -> dict:
    """Everything the dashboard header needs."""
    # TODO(M4): read user_stats, compute next_level_xp from 100 * n^1.5.
    return {
        "xp": 0, "level": 1, "next_level_xp": 283, "coins": 0,
        "current_streak": 0, "longest_streak": 0, "total_learning_seconds": 0,
    }


@router.get("/me/badges")
def my_badges(user: CurrentUser) -> dict:
    """Earned badges plus locked ones with progress toward them."""
    # TODO(M4): left join badges with user_badges.
    return {"earned": [], "locked": []}


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
