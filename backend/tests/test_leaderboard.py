"""Leaderboard: the period is real, names come in one query, opt-out is honoured.

Each test pins one thing the previous version got wrong. `period` was accepted
and ignored, so the two views were identical. Names were fetched one row at a
time. And a learner who asked not to be ranked publicly still was.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.gamification import UserStats, XPEvent
from app.models.user import User


class TestLeaderboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.selects = {"n": 0}

        @event.listens_for(cls.engine, "before_cursor_execute")
        def _count(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                cls.selects["n"] += 1

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        self.db = self.Session()
        self.me = uuid.uuid4()
        self.app = app
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.me), "email": "me@t.local", "role": "student", "full_name": "Me"
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.db.rollback()
        for model in (XPEvent, UserStats, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()

    def _learner(self, name, lifetime_xp, recent_xp=0, old_xp=0, opt_out=False, uid=None):
        uid = uid or uuid.uuid4()
        self.db.add(User(id=uid, email=f"{uid.hex[:8]}@t.local", full_name=name,
                         preferences={"leaderboard_opt_out": True} if opt_out else {}))
        self.db.add(UserStats(user_id=uid, xp=lifetime_xp, level=2, current_streak=3))
        now = datetime.now(timezone.utc)
        if recent_xp:
            self.db.add(XPEvent(id=uuid.uuid4(), user_id=uid, event_type="lesson.completed",
                                xp_awarded=recent_xp, created_at=now - timedelta(days=1)))
        if old_xp:
            self.db.add(XPEvent(id=uuid.uuid4(), user_id=uid, event_type="lesson.completed",
                                xp_awarded=old_xp, created_at=now - timedelta(days=30)))
        self.db.commit()
        return uid

    def test_weekly_and_all_time_actually_differ(self) -> None:
        """A veteran leads all-time; a newcomer who worked this week leads weekly."""
        self._learner("Veteran", lifetime_xp=5000, recent_xp=10, old_xp=4990)
        self._learner("Newcomer", lifetime_xp=300, recent_xp=300)

        weekly = self.client.get("/api/leaderboard?period=weekly").json()
        all_time = self.client.get("/api/leaderboard?period=all").json()

        self.assertEqual(weekly["items"][0]["name"], "Newcomer")
        self.assertEqual(all_time["items"][0]["name"], "Veteran")
        self.assertEqual(weekly["period"], "weekly")
        self.assertEqual(all_time["period"], "all")

    def test_weekly_counts_only_the_last_seven_days(self) -> None:
        self._learner("A", lifetime_xp=900, recent_xp=100, old_xp=800)
        row = self.client.get("/api/leaderboard?period=weekly").json()["items"][0]
        self.assertEqual(row["xp"], 100)

    def test_opting_out_hides_you_from_everyone_else(self) -> None:
        self._learner("Public", lifetime_xp=100, recent_xp=100)
        self._learner("Private", lifetime_xp=900, recent_xp=900, opt_out=True)
        names = [r["name"] for r in self.client.get("/api/leaderboard").json()["items"]]
        self.assertNotIn("Private", names)
        self.assertIn("Public", names)

    def test_but_you_still_see_your_own_rank(self) -> None:
        """Hiding you from others is not hiding you from yourself."""
        self._learner("Me", lifetime_xp=400, recent_xp=400, opt_out=True, uid=self.me)
        me = self.client.get("/api/leaderboard").json()["me"]
        self.assertIsNotNone(me)
        self.assertEqual(me["xp"], 400)
        self.assertTrue(me["opted_out"])

    def test_query_count_does_not_grow_with_the_board(self) -> None:
        """Names used to be fetched one row at a time."""
        counts = []
        for n in (2, 20):
            self.db.query(XPEvent).delete()
            self.db.query(UserStats).delete()
            self.db.query(User).delete()
            self.db.commit()
            for i in range(n):
                self._learner(f"L{i}", lifetime_xp=10 * (i + 1), recent_xp=10 * (i + 1))
            type(self).selects["n"] = 0
            self.client.get("/api/leaderboard")
            counts.append(type(self).selects["n"])
        self.assertEqual(counts[0], counts[1], counts)

    def test_nobody_with_zero_xp_is_ranked(self) -> None:
        self._learner("Idle", lifetime_xp=0)
        self.assertEqual(self.client.get("/api/leaderboard").json()["items"], [])


if __name__ == "__main__":
    unittest.main()
