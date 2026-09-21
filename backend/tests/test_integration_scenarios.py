"""Integration verification tests for Member 4 (Gamification & Analytics).

Verifies end-to-end event integration across application scenarios:
Scenario 1: User completes lesson -> lesson.completed -> +50 XP -> xp_events row
Scenario 2: User submits 5-question quiz with 3 correct -> quiz.submitted -> +25 XP -> xp_events row
Scenario 3: User gets perfect 5/5 -> +60 XP
Scenario 4: User enrolls in course -> +20 XP
Scenario 5: User sends enough tutor messages to count as a tutor session -> +5 XP -> repeated stop at +25/day
Scenario 6: Daily login -> +10 XP (plus streak bonus)
Scenario 7: An Event Bus handler throws an exception -> operation still succeeds -> error is logged
Scenario 8: User has no existing user_stats row -> created automatically without crashing
"""

from __future__ import annotations

import unittest
import uuid
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.gamification import UserStats, XPEvent
from app.models.user import User
from app.services.events import clear_handlers, emit, register_handler
from app.services.xp_engine import (
    TUTOR_XP_DAILY_CAP,
    register_xp_handlers,
)


class TestIntegrationScenarios(unittest.TestCase):
    """Verifies all 8 Member 4 Week 1 integration scenarios."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create in-memory SQLite database for integration verification."""
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self) -> None:
        """Prepare clean session, test user, and registered handlers."""
        self.db: Session = self.SessionLocal()
        clear_handlers()
        register_xp_handlers()

        self.user_id = uuid.uuid4()
        self.user = User(
            id=self.user_id,
            email=f"student_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Scenario Student",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        clear_handlers()

    def test_scenario_1_lesson_completed(self) -> None:
        """Scenario 1: User completes lesson -> lesson.completed -> +50 XP -> xp_events row."""
        lesson_id = str(uuid.uuid4())
        course_id = str(uuid.uuid4())

        emit(
            db=self.db,
            user_id=self.user_id,
            event_type="lesson.completed",
            payload={"lesson_id": lesson_id, "course_id": course_id},
        )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 50)

        event = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "lesson.completed")
            .first()
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.xp_awarded, 50)
        self.assertEqual(str(event.ref_id), lesson_id)

    def test_scenario_2_quiz_3_of_5_correct(self) -> None:
        """Scenario 2: User submits 5-question quiz with 3 correct -> +25 XP -> xp_events row."""
        quiz_id = str(uuid.uuid4())
        attempt_id = str(uuid.uuid4())

        emit(
            db=self.db,
            user_id=self.user_id,
            event_type="quiz.submitted",
            payload={
                "quiz_id": quiz_id,
                "attempt_id": attempt_id,
                "correct_count": 3,
                "total_questions": 5,
            },
        )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        # 10 base + (3 * 5) = 25 XP
        self.assertEqual(stats.xp, 25)

        event = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "quiz.submitted")
            .first()
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.xp_awarded, 25)

    def test_scenario_3_quiz_perfect_5_of_5(self) -> None:
        """Scenario 3: User gets perfect 5/5 -> +60 XP."""
        quiz_id = str(uuid.uuid4())
        attempt_id = str(uuid.uuid4())

        emit(
            db=self.db,
            user_id=self.user_id,
            event_type="quiz.submitted",
            payload={
                "quiz_id": quiz_id,
                "attempt_id": attempt_id,
                "correct_count": 5,
                "total_questions": 5,
            },
        )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        # 10 base + (5 * 5) + 25 perfect bonus = 60 XP
        self.assertEqual(stats.xp, 60)

    def test_scenario_4_course_enrolled(self) -> None:
        """Scenario 4: User enrolls in course -> +20 XP."""
        course_id = str(uuid.uuid4())

        emit(
            db=self.db,
            user_id=self.user_id,
            event_type="course.enrolled",
            payload={"course_id": course_id},
        )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 20)

        event = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "course.enrolled")
            .first()
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.xp_awarded, 20)

    def test_scenario_5_tutor_sessions_and_daily_cap(self) -> None:
        """Scenario 5: Tutor session awards +5 XP; repeated sessions stop at +25/day."""
        for i in range(7):
            conv_id = str(uuid.uuid4())
            emit(
                db=self.db,
                user_id=self.user_id,
                event_type="tutor.session",
                payload={"conversation_id": conv_id, "message_count": 3},
            )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        # 5 sessions * 5 XP = 25 XP (sessions 6 and 7 awarded 0 XP due to cap)
        self.assertEqual(stats.xp, TUTOR_XP_DAILY_CAP)

        events = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "tutor.session")
            .all()
        )
        total_awarded = sum(e.xp_awarded for e in events)
        self.assertEqual(total_awarded, 25)

    def test_scenario_6_daily_login(self) -> None:
        """Scenario 6: Daily login gives +10 XP plus streak bonus."""
        emit(
            db=self.db,
            user_id=self.user_id,
            event_type="daily.login",
            payload={"date": "2026-09-07"},
        )

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        # 10 base + 5 streak bonus (streak=1) = 15 XP
        self.assertEqual(stats.xp, 15)

    def test_scenario_7_event_handler_failure_isolation(self) -> None:
        """Scenario 7: Event Bus handler throws an exception -> operation succeeds and logs error."""
        @register_handler("lesson.completed")
        def crashing_handler(db: Any, user_id: Any, payload: dict[str, Any]) -> None:
            raise ValueError("Deliberate handler crash in analytics listener")

        lesson_id = str(uuid.uuid4())

        # Calling emit must not crash the caller
        try:
            emit(
                db=self.db,
                user_id=self.user_id,
                event_type="lesson.completed",
                payload={"lesson_id": lesson_id, "course_id": str(uuid.uuid4())},
            )
        except Exception as err:
            self.fail(f"emit() allowed a handler exception to escape: {err}")

        # The XP engine handler still ran successfully
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 50)

    def test_scenario_8_missing_user_stats_auto_created(self) -> None:
        """Scenario 8: User has no existing user_stats row -> created automatically without crashing."""
        fresh_user_id = uuid.uuid4()
        fresh_user = User(
            id=fresh_user_id,
            email=f"fresh_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Fresh User",
        )
        self.db.add(fresh_user)
        self.db.commit()

        # Verify no user_stats row exists initially
        initial_stats = self.db.query(UserStats).filter(UserStats.user_id == fresh_user_id).first()
        self.assertIsNone(initial_stats)

        # Trigger event
        emit(
            db=self.db,
            user_id=fresh_user_id,
            event_type="course.enrolled",
            payload={"course_id": str(uuid.uuid4())},
        )

        # Verify user_stats was created on-demand
        created_stats = self.db.query(UserStats).filter(UserStats.user_id == fresh_user_id).first()
        self.assertIsNotNone(created_stats)
        self.assertEqual(created_stats.xp, 20)
        self.assertEqual(created_stats.level, 1)

    def test_quiz_generated_supported_on_event_bus(self) -> None:
        """Verify quiz.generated event is supported by Event Bus without crashing."""
        generated_quiz_id = str(uuid.uuid4())
        results = emit(
            db=self.db,
            user_id=self.user_id,
            event_type="quiz.generated",
            payload={"quiz_id": generated_quiz_id, "topic": "databases.normalization"},
        )
        self.assertEqual(results, [])

    def test_api_me_stats_endpoint(self) -> None:
        """Verify GET /api/me/stats logic returns real UserStats data."""
        from app.routers.gamification import my_stats

        # Before XP
        data1 = my_stats(user={"id": str(self.user_id)}, db=self.db)
        self.assertEqual(data1["xp"], 0)
        self.assertEqual(data1["level"], 1)

        # Award XP via Event Bus
        emit(self.db, self.user_id, "lesson.completed", {"lesson_id": str(uuid.uuid4())})

        # After XP
        data2 = my_stats(user={"id": str(self.user_id)}, db=self.db)
        self.assertEqual(data2["xp"], 50)
        self.assertEqual(data2["level"], 1)
        self.assertEqual(data2["next_level_xp"], 282)

    def test_http_api_me_stats_and_achievements_with_testclient(self) -> None:
        """Verify GET /api/me/stats and GET /api/me/achievements over HTTP using TestClient."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.database import get_db
        from app.deps import get_current_user
        from app.seed.seed_data import seed_badges

        # Seed badges into the test db
        seed_badges(self.db)

        # Override dependencies
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id),
            "email": self.user.email,
            "role": "student",
        }

        try:
            client = TestClient(app)

            # Test GET /api/me/stats
            stats_resp = client.get("/api/me/stats")
            self.assertEqual(stats_resp.status_code, 200)
            stats_json = stats_resp.json()
            self.assertIn("xp", stats_json)
            self.assertIn("level", stats_json)
            self.assertIn("current_streak", stats_json)
            self.assertEqual(stats_json["next_level_xp"], 282)

            # Test GET /api/me/achievements
            achieve_resp = client.get("/api/me/achievements")
            self.assertEqual(achieve_resp.status_code, 200)
            achieve_json = achieve_resp.json()
            self.assertIn("earned", achieve_json)
            self.assertIn("locked", achieve_json)
            self.assertEqual(achieve_json["total_badges"], 2)

            # Also verify /api/me/badges alias
            badges_resp = client.get("/api/me/badges")
            self.assertEqual(badges_resp.status_code, 200)

        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    unittest.main()
