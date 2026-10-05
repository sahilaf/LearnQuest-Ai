"""Regression tests for two authentication holes found in review (2026-10-06).

1. `Bearer dev:<id>:admin@learnquest.ai` made anyone the administrator, even
   with anonymous dev mode off - dev tokens carry no signature at all.
2. In dev mode, a token that failed verification was read *unverified*, so a
   hand-made JWT could name any user's id.

No network and no database: the user sync is replaced with an echo of the
identity the token claims, which is exactly what an attacker would get.
"""

from __future__ import annotations

import time
import unittest
import uuid
from unittest.mock import patch

import jwt
from fastapi import HTTPException

from app import deps
from app.config import settings


def _echo_user(user_id, email, full_name=None, avatar_url=None, default_role="student"):  # noqa: ANN001
    return {"id": str(user_id), "email": email, "role": default_role}


def _forged_jwt(sub: str) -> str:
    """A well-formed JWT signed with a key the server has never seen."""
    return jwt.encode(
        {"sub": sub, "email": "victim@example.com", "aud": "authenticated", "exp": int(time.time()) + 600},
        "attacker-secret-not-the-real-one",
        algorithm="HS256",
    )


class AuthHardeningTests(unittest.TestCase):
    def _auth(self, header, *, anonymous: bool, secret: str = "real-secret", url: str = ""):
        with patch.object(type(settings), "allow_anonymous", property(lambda s: anonymous)), \
                patch.object(settings, "supabase_jwt_secret", secret), \
                patch.object(settings, "supabase_url", url), \
                patch.object(deps, "_sync_user_in_db", _echo_user), \
                patch.object(deps, "get_jwks_client", lambda: None):
            return deps.get_current_user(header)

    # --- 1. dev tokens --------------------------------------------------------

    def test_dev_admin_token_is_refused_outside_dev_mode(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._auth(f"Bearer dev:{uuid.uuid4()}:admin@learnquest.ai", anonymous=False)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_dev_token_still_works_in_dev_mode(self) -> None:
        uid = uuid.uuid4()
        user = self._auth(f"Bearer dev:{uid}:me@learnquest.local", anonymous=True)
        self.assertEqual(user["id"], str(uid))

    # --- 2. unverifiable JWTs ---------------------------------------------------

    def test_forged_jwt_is_refused_in_production(self) -> None:
        with self.assertRaises(HTTPException):
            self._auth(f"Bearer {_forged_jwt(str(uuid.uuid4()))}", anonymous=False)

    def test_forged_jwt_is_refused_in_dev_mode_when_a_secret_is_configured(self) -> None:
        """The old code read it unverified and logged the attacker in as `sub`."""
        victim = str(uuid.uuid4())
        with self.assertRaises(HTTPException):
            self._auth(f"Bearer {_forged_jwt(victim)}", anonymous=True, secret="real-secret")

    def test_forged_jwt_is_refused_in_dev_mode_when_only_the_url_is_configured(self) -> None:
        with self.assertRaises(HTTPException):
            self._auth(
                f"Bearer {_forged_jwt(str(uuid.uuid4()))}",
                anonymous=True, secret="", url="https://project.supabase.co",
            )

    def test_bare_dev_box_still_accepts_local_sign_in(self) -> None:
        """No secret and no URL: nothing to verify with, so dev keeps working."""
        uid = str(uuid.uuid4())
        user = self._auth(f"Bearer {_forged_jwt(uid)}", anonymous=True, secret="", url="")
        self.assertEqual(user["id"], uid)

    def test_no_token_is_401_outside_dev_mode(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._auth(None, anonymous=False)
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
