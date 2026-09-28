"""XP, badges, streaks, challenges, leaderboard.

OWNER: Member 4. See plan.md 9.8.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser
from app.models.gamification import Badge, UserBadge, UserStats, XPEvent
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
def todays_challenges(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict:
    """Three challenges for today with the caller's progress."""
    if not db or not user or "id" not in user:
        return {"items": []}
    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        return {"items": []}

    from app.services.challenges import get_user_challenges_for_today

    items = get_user_challenges_for_today(db, user_uuid)
    return {"items": items}


@router.post("/challenges/{challenge_id}/claim")
def claim_challenge_endpoint(
    challenge_id: str, user: CurrentUser, db: Session | None = Depends(get_db)
) -> dict:
    """Claim reward for a completed daily challenge."""
    if not db or not user or "id" not in user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        user_uuid = uuid.UUID(str(user["id"]))
        ch_uuid = uuid.UUID(challenge_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format.")

    from app.services.challenges import claim_challenge

    try:
        result = claim_challenge(db, user_uuid, ch_uuid)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


LEADERBOARD_SIZE = 50
WEEK = 7


@router.get("/leaderboard")
def leaderboard(
    user: CurrentUser,
    scope: str = "global",
    period: str = "weekly",
    db: Session | None = Depends(get_db),
) -> dict:
    """Top 50 plus the caller's own rank, pinned even when outside the top 50.

    period  weekly - XP earned in the last 7 days, summed from xp_events. This
                     is why every award must write an event row: the weekly
                     board is computed from them.
            all    - lifetime XP from user_stats.

    Three things this used to get wrong:
      - `period` was accepted and echoed back but never applied, so "this week"
        and "all time" returned identical rankings;
      - each row looked its user's name up separately - up to fifty queries, a
        few seconds against the remote database;
      - `preferences.leaderboard_opt_out` was not honoured, so a learner who
        asked not to be ranked publicly still was.
    """
    from sqlalchemy import func

    from app.models.user import User as UserModel

    user_uuid = None
    if user and "id" in user:
        try:
            user_uuid = uuid.UUID(str(user["id"]))
        except ValueError:
            user_uuid = None

    if not db:
        return {"items": [], "me": None, "scope": scope, "period": period}

    weekly = period != "all"

    if weekly:
        since = datetime.now(timezone.utc) - timedelta(days=WEEK)
        totals = dict(
            db.query(XPEvent.user_id, func.coalesce(func.sum(XPEvent.xp_awarded), 0))
            .filter(XPEvent.created_at >= since)
            .group_by(XPEvent.user_id)
            .all()
        )
    else:
        totals = dict(db.query(UserStats.user_id, UserStats.xp).all())

    # One query for everyone's name, level, streak and privacy preference -
    # not one per row.
    people = {
        u.id: u
        for u in db.query(UserModel).filter(UserModel.id.in_(list(totals) or [None])).all()
    }
    stats = {
        s.user_id: s
        for s in db.query(UserStats).filter(UserStats.user_id.in_(list(totals) or [None])).all()
    }

    def opted_out(uid) -> bool:
        prefs = getattr(people.get(uid), "preferences", None) or {}
        return bool(prefs.get("leaderboard_opt_out"))

    ranked = sorted(
        ((uid, int(xp or 0)) for uid, xp in totals.items() if int(xp or 0) > 0),
        key=lambda pair: pair[1],
        reverse=True,
    )

    def entry(rank, uid, xp):
        person, stat = people.get(uid), stats.get(uid)
        return {
            "rank": rank,
            "user_id": str(uid),
            "name": (person.full_name if person and person.full_name else "Learner"),
            "xp": xp,
            "level": stat.level if stat else 1,
            "streak": stat.current_streak if stat else 0,
        }

    public = [(uid, xp) for uid, xp in ranked if not opted_out(uid)]
    items = [entry(rank, uid, xp) for rank, (uid, xp) in enumerate(public[:LEADERBOARD_SIZE], 1)]

    # The caller always sees their own rank - including when they have opted
    # out of the public board, since hiding you from others is not hiding you
    # from yourself.
    me_entry = None
    if user_uuid is not None:
        mine = int(totals.get(user_uuid, 0) or 0)
        better = sum(1 for uid, xp in public if xp > mine and uid != user_uuid)
        me_entry = entry(better + 1, user_uuid, mine)
        if not people.get(user_uuid):
            me_entry["name"] = user.get("full_name") or "You"
        me_entry["opted_out"] = opted_out(user_uuid)

    return {"items": items, "me": me_entry, "scope": scope, "period": "weekly" if weekly else "all"}


@router.get("/notifications")
def notifications(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict:
    """In-app notifications for authenticated learner."""
    if not db or not user or "id" not in user:
        return {"items": [], "unread": 0}
    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        return {"items": [], "unread": 0}

    from app.models.gamification import Notification

    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user_uuid)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == user_uuid, Notification.is_read == False)
        .count()
    )

    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifs
        ],
        "unread": unread_count,
    }


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: str, user: CurrentUser, db: Session | None = Depends(get_db)
) -> dict:
    """Mark single notification as read, guarded by user ownership."""
    if not db or not user or "id" not in user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        user_uuid = uuid.UUID(str(user["id"]))
        notif_uuid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID.")

    from app.models.gamification import Notification

    notif = db.query(Notification).filter(Notification.id == notif_uuid).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    if notif.user_id != user_uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    notif.is_read = True
    db.commit()
    return {"id": str(notif.id), "is_read": True}


@router.post("/notifications/read-all")
def mark_all_read(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict:
    """Mark all unread notifications as read for current user."""
    if not db or not user or "id" not in user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID.")

    from app.models.gamification import Notification

    db.query(Notification).filter(
        Notification.user_id == user_uuid, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"success": True}
