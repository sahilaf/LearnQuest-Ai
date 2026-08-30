"""Profile and preferences.

OWNER: Member 3. See plan.md 8.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me")
def get_me(user: CurrentUser) -> dict:
    """Profile plus gamification stats (M4 supplies the stats block)."""
    # TODO(M3): join users with user_stats.
    return {"user": user, "stats": None}


@router.patch("/me")
def update_me(user: CurrentUser, payload: dict) -> dict:
    """Update full_name, avatar_url and preferences."""
    # TODO(M3): validate with a Pydantic schema, never trust raw dicts in production.
    return {"user": user, "updated": list(payload.keys())}
