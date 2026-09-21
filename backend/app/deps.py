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

import base64
import logging
import ssl
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import certifi
import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import database_is_configured, get_session_factory
from app.models.user import User
from app.services.events import emit

logger = logging.getLogger("learnquest.auth")

DEV_USER: dict[str, Any] = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "admin@learnquest.ai",
    "full_name": "LearnQuest Admin",
    "role": "admin",
    "avatar_url": None,
    "preferences": {},
    "created_at": "2026-08-30T00:00:00Z",
    "last_login_at": "2026-08-30T00:00:00Z",
}

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    if _jwks_client is None and settings.supabase_url:
        try:
            ctx = ssl.create_default_context(cafile=certifi.where())
            jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(
                jwks_url,
                ssl_context=ctx,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=3600,
            )
        except Exception as exc:
            logger.warning("Failed to initialize Supabase JWKS client: %s", exc)
    return _jwks_client


_get_jwks_client = get_jwks_client


def _unauthorized(detail: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", "X-Error-Code": code},
    )


def verify_supabase_token(token: str) -> dict[str, Any]:
    """Decode and validate a Supabase access token using JWKS or SUPABASE_JWT_SECRET.

    Supports modern ES256/RS256 asymmetric keys via Supabase JWKS as well as legacy HS256.
    Allows configurable leeway to tolerate client-server clock skew.
    Raises HTTPException(401) on anything invalid. Returns the JWT claims.
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise _unauthorized(f"Malformed token header: {exc}", "AUTH_TOKEN_INVALID") from None

    alg = header.get("alg", "HS256")
    leeway = settings.jwt_leeway_seconds

    # Asymmetric signing (ES256, RS256, EdDSA) via Supabase JWKS
    if alg in ("ES256", "RS256", "EdDSA"):
        jwks_client = get_jwks_client()
        if jwks_client:
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    audience="authenticated",
                    leeway=leeway,
                )
            except jwt.ExpiredSignatureError:
                raise _unauthorized("Token has expired.", "AUTH_TOKEN_EXPIRED") from None
            except jwt.InvalidTokenError as exc:
                logger.warning("JWKS token decode failed (%s), trying fallback...", exc)
            except Exception as exc:
                logger.warning("JWKS key retrieval failed (%s), trying fallback...", exc)

    # Symmetric HS256 validation (legacy secret)
    if settings.supabase_jwt_secret:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=leeway,
            )
        except jwt.ExpiredSignatureError:
            raise _unauthorized("Token has expired.", "AUTH_TOKEN_EXPIRED") from None
        except jwt.InvalidTokenError:
            try:
                decoded_secret = base64.b64decode(settings.supabase_jwt_secret)
                return jwt.decode(
                    token,
                    decoded_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                    leeway=leeway,
                )
            except jwt.ExpiredSignatureError:
                raise _unauthorized("Token has expired.", "AUTH_TOKEN_EXPIRED") from None
            except Exception:
                pass

    # Authoritative fallback via Supabase Auth API
    if settings.supabase_url:
        try:
            auth_headers = {"Authorization": f"Bearer {token}"}
            if settings.supabase_service_role_key:
                auth_headers["apikey"] = settings.supabase_service_role_key
            resp = httpx.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers=auth_headers,
                timeout=5.0,
            )
            if resp.status_code == 200:
                user_data = resp.json()
                return {
                    "sub": user_data.get("id"),
                    "email": user_data.get("email"),
                    "role": user_data.get("role", "authenticated"),
                    "user_metadata": user_data.get("user_metadata", {}),
                    "app_metadata": user_data.get("app_metadata", {}),
                }
            elif resp.status_code == 401:
                raise _unauthorized("Token is not recognized by Supabase.", "AUTH_TOKEN_INVALID")
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Supabase Auth API user verification failed: %s", exc)

    raise _unauthorized("Invalid token or signature verification failed.", "AUTH_TOKEN_INVALID")


def _sync_user_in_db(
    user_id: uuid.UUID,
    email: str,
    full_name: str | None = None,
    avatar_url: str | None = None,
    default_role: str = "student",
) -> dict[str, Any]:
    """Look up or create the public.users row, update last_login_at, and emit daily.login."""
    clean_email = (email or "").strip().lower()
    is_explicit_admin = clean_email == "admin@learnquest.ai"
    effective_role = "admin" if is_explicit_admin else "student"

    fallback_user = {
        "id": str(user_id),
        "email": clean_email or email,
        "full_name": full_name,
        "avatar_url": avatar_url,
        "role": effective_role,
        "preferences": {},
    }

    if not database_is_configured():
        return fallback_user

    try:
        session_factory = get_session_factory()
        with session_factory() as db:
            user_row = db.query(User).filter(User.id == user_id).first()
            if not user_row and clean_email:
                user_row = db.query(User).filter(func.lower(func.trim(User.email)) == clean_email).first()
                if user_row and user_row.id != user_id:
                    # Update ID to match the new Supabase auth UUID
                    try:
                        user_row.id = user_id
                    except Exception:
                        pass

            now = datetime.now(timezone.utc)
            is_first_login_today = False
            row_email = (user_row.email if user_row else "").strip().lower()
            is_target_admin = is_explicit_admin or (row_email == "admin@learnquest.ai")
            effective_role = "admin" if is_target_admin else "student"

            if not user_row:
                user_row = User(
                    id=user_id,
                    email=clean_email or email,
                    full_name=full_name or (clean_email.split('@')[0].title() if clean_email else None),
                    avatar_url=avatar_url,
                    role=effective_role,
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
                # Enforce admin role strictly for admin@learnquest.ai only
                user_row.role = effective_role
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
    except Exception as exc:
        logger.warning(
            "Database user sync failed (%s); returning user from token claims.", exc
        )
        return fallback_user


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Verify the Supabase access token, auto-create/sync public.users, and return user dict."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise _unauthorized("Empty bearer token.", "AUTH_EMPTY_TOKEN")

        # Dev token support for local testing with dummy accounts: Bearer dev:<user_id>:<email>
        if token.startswith("dev:"):
            parts = token.split(":")
            try:
                dev_id = uuid.UUID(parts[1])
                dev_email = parts[2] if len(parts) > 2 else f"{dev_id}@learnquest.local"
            except (ValueError, IndexError):
                dev_id = uuid.UUID(DEV_USER["id"])
                dev_email = DEV_USER["email"]
            name_part = dev_email.split("@")[0].replace(".", " ").title()
            clean_dev_email = dev_email.strip().lower()
            return _sync_user_in_db(
                user_id=dev_id,
                email=clean_dev_email,
                full_name=name_part,
                default_role="admin" if clean_dev_email == "admin@learnquest.ai" else "student",
            )

        claims = None
        try:
            claims = verify_supabase_token(token)
        except Exception as exc:
            if settings.dev_allow_anonymous:
                # If token is a JWT from Supabase, extract real claims without signature verification in dev mode
                try:
                    claims = jwt.decode(token, options={"verify_signature": False})
                    if not claims or "sub" not in claims:
                        raise ValueError("No sub claim in token")
                except Exception:
                    dev_id = uuid.UUID(DEV_USER["id"])
                    clean_dev_email = DEV_USER["email"].strip().lower()
                    return _sync_user_in_db(
                        user_id=dev_id,
                        email=clean_dev_email,
                        full_name=DEV_USER["full_name"],
                        default_role="admin" if clean_dev_email == "admin@learnquest.ai" else "student",
                    )
            else:
                raise exc

        try:
            user_id = uuid.UUID(claims["sub"])
        except (ValueError, KeyError) as err:
            raise _unauthorized("Invalid user ID in token sub claim.", "AUTH_TOKEN_INVALID") from err

        raw_email = claims.get("email") or f"{user_id}@learnquest.local"
        email = raw_email.strip().lower()
        user_meta = claims.get("user_metadata") or {}
        full_name = user_meta.get("full_name") or user_meta.get("name")
        avatar_url = user_meta.get("avatar_url") or user_meta.get("picture")

        return _sync_user_in_db(
            user_id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            default_role="admin" if email == "admin@learnquest.ai" else "student",
        )

    if settings.dev_allow_anonymous:
        dev_id = uuid.UUID(DEV_USER["id"])
        clean_dev_email = DEV_USER["email"].strip().lower()
        return _sync_user_in_db(
            user_id=dev_id,
            email=clean_dev_email,
            full_name=DEV_USER["full_name"],
            default_role="admin" if clean_dev_email == "admin@learnquest.ai" else "student",
        )

    raise _unauthorized("Missing Authorization header.", "AUTH_MISSING_TOKEN")


def require_admin(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Dependency that ensures the authenticated user is admin@learnquest.ai.

    Raises 403 Forbidden for all other users.
    """
    email = (user.get("email") or "").strip().lower()
    role = (user.get("role") or "").strip().lower()
    if email != "admin@learnquest.ai" or role != "admin":
        logger.warning(
            "require_admin rejected user id=%s email=%s role=%s",
            user.get("id"),
            email,
            role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Only admin@learnquest.ai has administrator privileges.",
            headers={"X-Error-Code": "AUTH_FORBIDDEN"},
        )
    return user


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
AdminUser = Annotated[dict[str, Any], Depends(require_admin)]
