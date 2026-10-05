"""Topic mastery and misconceptions. OWNER: Member 1. See plan.md 6.5, 6.10.

Separate from analytics.py (Member 4) so ownership stays clean: that router
serves aggregate dashboards, this one serves the misconception model that the
tutor reads from.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser
from app.models.ai import TopicMastery
from app.services.mastery import misconception_status

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


def _user_uuid(user: Any) -> uuid.UUID:
    raw = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user."
        ) from exc


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return db


@router.get("/me/misconceptions")
def my_misconceptions(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
    include_cleared: bool = Query(
        default=True,
        description="Include misconceptions the student has already overcome.",
    ),
) -> dict[str, Any]:
    """Every false belief recorded for this student, with its decay status.

    Status is derived, never stored:
      active  - captured, no correct answers since
      fading  - at least one correct answer since
      cleared - enough correct answers to consider it overcome
    """
    database = _require_db(db)
    user_id = _user_uuid(user)

    rows = (
        database.query(TopicMastery)
        .filter(TopicMastery.user_id == user_id, TopicMastery.misconception.isnot(None))
        .order_by(TopicMastery.misconception_updated_at.desc().nullslast())
        .all()
    )

    items = []
    for row in rows:
        state = misconception_status(row)
        if state == "cleared" and not include_cleared:
            continue
        items.append(
            {
                "topic_tag": row.topic_tag,
                "misconception": row.misconception,
                "status": state,
                "mastery_score": float(row.mastery_score or 0),
                "correct_streak": row.misconception_correct_streak or 0,
                "captured_at": (
                    row.misconception_updated_at.isoformat()
                    if row.misconception_updated_at
                    else None
                ),
                "cleared_at": (
                    row.misconception_cleared_at.isoformat()
                    if row.misconception_cleared_at
                    else None
                ),
            }
        )

    counts = {"active": 0, "fading": 0, "cleared": 0}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {"items": items, "total": len(items), "counts": counts}


@router.get("/me")
def my_mastery(
    user: CurrentUser, db: Session | None = Depends(get_db)
) -> dict[str, Any]:
    """Mastery score per topic, weakest first - what the roadmap plans around."""
    database = _require_db(db)
    user_id = _user_uuid(user)

    rows = (
        database.query(TopicMastery)
        .filter(TopicMastery.user_id == user_id)
        .order_by(TopicMastery.mastery_score.asc())
        .all()
    )

    return {
        "items": [
            {
                "topic_tag": r.topic_tag,
                "mastery_score": float(r.mastery_score or 0),
                "attempts": r.attempts or 0,
                "correct": r.correct or 0,
                "has_misconception": misconception_status(r) in ("active", "fading"),
                "last_practiced_at": (
                    r.last_practiced_at.isoformat() if r.last_practiced_at else None
                ),
            }
            for r in rows
        ],
        "total": len(rows),
    }
