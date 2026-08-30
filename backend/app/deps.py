"""Shared FastAPI dependencies.

OWNER: Member 3. Everyone else imports from here - do not redefine auth in your router.

    from app.deps import CurrentUser, AdminUser
    @router.get("/api/me/thing")
    def read(user: CurrentUser): ...

Until Firebase is wired up (M3, week 1 day 3), DEV_ALLOW_ANONYMOUS=true returns a
stub dev user so the other members are not blocked.
"""

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from app.config import settings

DEV_USER: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
    "firebase_uid": "dev-uid",
    "email": "dev@learnquest.local",
    "full_name": "Dev User",
    "role": "admin",
    "preferences": {},
}


def _unauthorized(detail: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", "X-Error-Code": code},
    )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Verify the Firebase ID token and return the matching user.

    TODO(M3): verify with firebase_admin.auth.verify_id_token, then upsert into
    the users table and return the ORM object instead of this dict.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise _unauthorized("Empty bearer token.", "AUTH_EMPTY_TOKEN")
        # TODO(M3): real verification goes here.
        if settings.dev_allow_anonymous:
            return DEV_USER
        raise _unauthorized("Token verification is not configured.", "AUTH_NOT_CONFIGURED")

    if settings.dev_allow_anonymous:
        return DEV_USER

    raise _unauthorized("Missing Authorization header.", "AUTH_MISSING_TOKEN")


def require_admin(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
            headers={"X-Error-Code": "AUTH_FORBIDDEN"},
        )
    return user


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
AdminUser = Annotated[dict[str, Any], Depends(require_admin)]
