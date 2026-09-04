"""Authentication routes.

OWNER: Member 3. See plan.md §8.3.
"""

from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas.user import SyncUserResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/sync", response_model=SyncUserResponse)
def sync_user(user: CurrentUser) -> dict:
    """Upsert the user from the verified Supabase token and return the profile."""
    return {"user": UserResponse.model_validate(user), "created": False}
