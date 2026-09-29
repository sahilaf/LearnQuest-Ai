"""Connection pool exhaustion, 2026-09-29.

"QueuePool limit of size 5 overflow 10 reached" took down the review page. Two
causes, each pinned here:

  - requests held a pooled connection through slow AI calls;
    `release_connection` hands it back before the await;
  - the login check wrote users.last_login_at on EVERY request, so parallel
    requests from one user queued on that row's lock, each holding a
    connection. It now writes only when something changed.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.database import Base, release_connection
from app.models.user import User


class _DB(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.statements: list[str] = []

        @event.listens_for(self.engine, "before_cursor_execute")
        def _record(conn, cursor, statement, params, context, executemany):
            self.statements.append(statement.strip().split()[0].upper())

    def tearDown(self) -> None:
        self.engine.dispose()


class TestReleaseConnection(_DB):
    def test_it_ends_the_transaction_and_keeps_the_work(self) -> None:
        db = self.Session()
        uid = uuid.uuid4()
        db.add(User(id=uid, email="a@t.local", full_name="A"))
        db.flush()
        self.assertTrue(db.in_transaction())

        release_connection(db)

        self.assertFalse(db.in_transaction())  # connection is back in the pool
        other = self.Session()
        self.assertIsNotNone(other.get(User, uid))  # and the row was committed
        db.close()
        other.close()

    def test_none_is_a_no_op(self) -> None:
        release_connection(None)


class TestLoginSyncWrites(_DB):
    def _sync(self, uid):
        with patch.object(deps, "get_session_factory", return_value=self.Session), patch.object(
            deps, "database_is_configured", return_value=True
        ), patch.object(deps, "emit"):
            return deps._sync_user_in_db(uid, "learner@t.local", "Learner")

    def _seed(self, last_login):
        uid = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=uid, email="learner@t.local", full_name="Learner",
                        role="student", last_login_at=last_login))
            db.commit()
        self.statements.clear()
        return uid

    def test_a_recent_login_is_one_read_and_no_write(self) -> None:
        uid = self._seed(datetime.now(timezone.utc) - timedelta(minutes=5))
        user = self._sync(uid)
        self.assertEqual(user["email"], "learner@t.local")
        self.assertNotIn("UPDATE", self.statements)
        self.assertEqual(self.statements.count("SELECT"), 1)

    def test_an_hour_old_login_is_refreshed(self) -> None:
        uid = self._seed(datetime.now(timezone.utc) - timedelta(hours=2))
        self._sync(uid)
        self.assertIn("UPDATE", self.statements)

    def test_first_request_of_the_day_still_counts_as_a_daily_login(self) -> None:
        uid = self._seed(datetime.now(timezone.utc) - timedelta(days=1))
        with patch.object(deps, "get_session_factory", return_value=self.Session), patch.object(
            deps, "database_is_configured", return_value=True
        ), patch.object(deps, "emit") as emit:
            deps._sync_user_in_db(uid, "learner@t.local", "Learner")
        emit.assert_called_once()
        self.assertEqual(emit.call_args.args[2], "daily.login")


if __name__ == "__main__":
    unittest.main()
