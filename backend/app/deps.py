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

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import database_is_configured, get_session_factory
from app.models.user import User
from app.services.events import emit

logger = logging.getLogger("learnquest.auth")

DEV_USER: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "dev@learnquest.local",
    "full_name": "Dev User",
    "role": "admin",
    "avatar_url": None,
    "preferences": {},
    "created_at": "2026-08-30T00:00:00Z",
    "last_login_at": "2026-08-30T00:00:00Z",
}


def _unauthorized(detail: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", "X-Error-Code": code},
    )


def verify_supabase_token(token: str) -> dict[str, Any]:
    """Decode and validate a Supabase access token locally using SUPABASE_JWT_SECRET.

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


def _sync_user_in_db(
    user_id: uuid.UUID,
    email: str,
    full_name: str | None = None,
    avatar_url: str | None = None,
    default_role: str = "student",
) -> dict[str, Any]:
    """Look up or create the public.users row, update last_login_at, and emit daily.login."""
    if not database_is_configured():
        return {
            "id": str(user_id),
            "email": email,
            "full_name": full_name,
            "avatar_url": avatar_url,
            "role": default_role,
            "preferences": {},
        }

    session_factory = get_session_factory()
    with session_factory() as db:
        user_row = db.query(User).filter(User.id == user_id).first()
        now = datetime.now(timezone.utc)
        is_first_login_today = False

        if not user_row:
            user_row = User(
                id=user_id,
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                role=default_role,
                preferences={},
                created_at=now,
                last_login_at=now,
            )
            db.add(user_row)
            db.commit()
            db.refresh(user_row)
            is_first_login_today = True
        else:
            if user_row.last_login_at is None or user_row.last_login_at.date() < now.date():
                is_first_login_today = True
            user_row.last_login_at = now
            if full_name and not user_row.full_name:
                user_row.full_name = full_name
            if avatar_url and not user_row.avatar_url:
                user_row.avatar_url = avatar_url
            db.commit()
            db.refresh(user_row)

        user_data = user_row.to_dict()

        if is_first_login_today:
            emit(db, user_row.id, "daily.login", {})

        return user_data


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Verify the Supabase access token, auto-create/sync public.users, and return user dict."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise _unauthorized("Empty bearer token.", "AUTH_EMPTY_TOKEN")

        if not settings.supabase_jwt_secret and settings.dev_allow_anonymous:
            # Running in dev mode with mock token or unconfigured secret
            dev_id = uuid.UUID(DEV_USER["id"])
            return _sync_user_in_db(
                user_id=dev_id,
                email=DEV_USER["email"],
                full_name=DEV_USER["full_name"],
                default_role="admin",
            )

        claims = verify_supabase_token(token)
        try:
            user_id = uuid.UUID(claims["sub"])
        except (ValueError, KeyError) as err:
            raise _unauthorized("Invalid user ID in token sub claim.", "AUTH_TOKEN_INVALID") from err

        email = claims.get("email") or f"{user_id}@learnquest.local"
        user_meta = claims.get("user_metadata") or {}
        full_name = user_meta.get("full_name") or user_meta.get("name")
        avatar_url = user_meta.get("avatar_url") or user_meta.get("picture")

        return _sync_user_in_db(
            user_id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            default_role="student",
        )

    if settings.dev_allow_anonymous:
        dev_id = uuid.UUID(DEV_USER["id"])
        return _sync_user_in_db(
            user_id=dev_id,
            email=DEV_USER["email"],
            full_name=DEV_USER["full_name"],
            default_role="admin",
        )

    raise _unauthorized("Missing Authorization header.", "AUTH_MISSING_TOKEN")


def require_admin(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Dependency that ensures the authenticated user has the 'admin' role.

    Raises 403 Forbidden for students.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
            headers={"X-Error-Code": "AUTH_FORBIDDEN"},
        )
    return user


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
AdminUser = Annotated[dict[str, Any], Depends(require_admin)]
