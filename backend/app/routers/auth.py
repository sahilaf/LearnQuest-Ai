"""Authentication routes.

OWNER: Member 3. See plan.md 8.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/sync")
def sync_user(user: CurrentUser) -> dict:
    """Upsert the user from the verified Supabase token and return the profile."""
    # TODO(M3): upsert into users, set last_login_at, emit("daily.login") once per day.
    return {"user": user, "created": False}
