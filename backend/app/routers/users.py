"""Profile and preferences.

OWNER: Member 3. See plan.md §8.3.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import database_is_configured, get_db
from app.deps import CurrentUser
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/api", tags=["users"])


def _stats_for(db: Session | None, user_id: Any) -> dict[str, Any] | None:
    """The gamification block for a profile, or None when there is none.

    This used to be hardcoded to None, so every profile rendered zero XP, level
    one and no streak - values that look like real data and are not. None is
    returned only when the learner genuinely has no stats row yet.
    """
    if db is None:
        return None
    try:
        from app.models.gamification import UserStats

        row = db.query(UserStats).filter(UserStats.user_id == uuid.UUID(str(user_id))).first()
    except Exception:  # noqa: BLE001 - a profile must still load without stats
        return None
    if row is None:
        return None
    return {
        "xp": row.xp,
        "level": row.level,
        "coins": row.coins,
        "current_streak": row.current_streak,
        "longest_streak": row.longest_streak,
        "total_learning_seconds": row.total_learning_seconds,
    }


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Profile plus gamification stats (M4 supplies the stats block)."""
    # If DB is configured, fetch latest User from DB
    if db and database_is_configured():
        user_uuid = uuid.UUID(user["id"])
        user_row = db.query(User).filter(User.id == user_uuid).first()
        if user_row:
            user_data = user_row.to_dict()
        else:
            user_data = user
    else:
        user_data = user

    return {
        "user": UserResponse.model_validate(user_data),
        "stats": _stats_for(db if database_is_configured() else None, user["id"]),
    }


@router.patch("/me", response_model=UserProfileResponse)
def update_me(
    payload: UserUpdate,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Update full_name, avatar_url and preferences."""
    user_data = dict(user)

    if db and database_is_configured():
        user_uuid = uuid.UUID(user["id"])
        user_row = db.query(User).filter(User.id == user_uuid).first()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if payload.full_name is not None:
            user_row.full_name = payload.full_name
        if payload.avatar_url is not None:
            user_row.avatar_url = payload.avatar_url
        if payload.preferences is not None:
            current_prefs = dict(user_row.preferences or {})
            current_prefs.update(payload.preferences)
            user_row.preferences = current_prefs

        db.commit()
        db.refresh(user_row)
        user_data = user_row.to_dict()
    else:
        if payload.full_name is not None:
            user_data["full_name"] = payload.full_name
        if payload.avatar_url is not None:
            user_data["avatar_url"] = payload.avatar_url
        if payload.preferences is not None:
            user_data["preferences"] = {**(user_data.get("preferences") or {}), **payload.preferences}

    return {"user": UserResponse.model_validate(user_data), "stats": _stats_for(db if database_is_configured() else None, user["id"])}


@router.get("/me/enrollments")
def get_my_enrollments(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """List courses the current user is enrolled in (Member 2)."""
    from app.routers.progress import my_enrollments
    return my_enrollments(user=user, db=db)

