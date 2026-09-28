"""Personalized recommendations. OWNER: Member 1. See services/recommender.py.

Every item carries a human-readable reason - never ship a recommendation without
one (plan.md 6.5). The reason is what makes it checkable, and what sells it.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


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


@router.get("")
def list_recommendations(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Ranked recommendations, each with the reason that ranked it. Cached 1h."""
    from app.services.recommender import recommend

    database = _require_db(db)
    items = recommend(database, _user_uuid(user), limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/{recommendation_id}/dismiss")
def dismiss(
    recommendation_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Hide a recommendation. It is not offered again."""
    from app.services.recommender import dismiss as _dismiss

    database = _require_db(db)
    if not _dismiss(database, _user_uuid(user), recommendation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
    return {"id": recommendation_id, "dismissed": True}


@router.get("/daily-plan")
def daily_plan(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
    minutes: int | None = Query(default=None, ge=5, le=240),
) -> dict[str, Any]:
    """A time-boxed plan: due reviews first, then lessons, then one quiz.

    Uses `preferences.daily_goal_minutes` when set and no `minutes` is given.
    """
    from app.models.user import User
    from app.services.recommender import daily_plan as _plan

    database = _require_db(db)
    user_uuid = _user_uuid(user)

    budget = minutes
    if budget is None:
        row = database.query(User).filter(User.id == user_uuid).first()
        prefs = (row.preferences or {}) if row is not None else {}
        try:
            budget = int(prefs.get("daily_goal_minutes") or 30)
        except (TypeError, ValueError):
            budget = 30

    return _plan(database, user_uuid, minutes=budget)
