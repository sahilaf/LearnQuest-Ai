"""Shared FastAPI dependencies.

OWNER: Member 3. Everyone else imports from here - do not redefine auth in your router.

    from app.deps import CurrentUser, AdminUser

    @router.get("/api/me/thing")
    def read(user: CurrentUser): ...

Auth is Supabase Auth. The frontend signs in with @supabase/supabase-js and sends
the returned access token as `Authorization: Bearer <jwt>`. We verify that JWT
locally with the project's JWT secret - no network round trip per request.

The token's `sub` claim IS the auth.users UUID, and public.users.id references it,
so there is no separate mirror column to keep in sync.

Until SUPABASE_JWT_SECRET is set (M3, week 1 day 3), DEV_ALLOW_ANONYMOUS=true
returns a stub dev user so the other members are not blocked.
"""

from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import settings

DEV_USER: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
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


def verify_supabase_token(token: str) -> dict[str, Any]:
    """Decode and validate a Supabase access token.

    Raises HTTPException(401) on anything invalid. Returns the JWT claims.
    """
    if not settings.supabase_jwt_secret:
        raise _unauthorized(
            "SUPABASE_JWT_SECRET is not configured.", "AUTH_NOT_CONFIGURED"
        )
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired.", "AUTH_TOKEN_EXPIRED") from None
    except jwt.InvalidTokenError as exc:
        raise _unauthorized(f"Invalid token: {exc}", "AUTH_TOKEN_INVALID") from None


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Verify the Supabase access token and return the matching user.

    TODO(M3): after decoding, look up public.users by id == claims["sub"], create
    the row on first login, and return the ORM object instead of this dict.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise _unauthorized("Empty bearer token.", "AUTH_EMPTY_TOKEN")

        if not settings.supabase_jwt_secret and settings.dev_allow_anonymous:
            return DEV_USER

        claims = verify_supabase_token(token)

        # TODO(M3): replace with a real users-table lookup / upsert.
        return {
            "id": claims["sub"],
            "email": claims.get("email"),
            "full_name": (claims.get("user_metadata") or {}).get("full_name"),
            # TODO(M3): role lives in public.users, not the token. Read it there.
            "role": "student",
            "preferences": {},
        }

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
