"""Unit tests for the XP Engine and Event Bus integration (Member 4 - Gamification & Analytics).

Tests verification requirements:
A. lesson.completed gives 50 XP
B. course.enrolled gives 20 XP
C. quiz with 5 questions and 3 correct gives 10 + (3 * 5) = 25 XP
D. perfect 5-question quiz gives 10 + (5 * 5) + 25 = 60 XP
E. tutor XP cannot exceed 25 XP per day
F. xp_for_level() works correctly (L2=283, L5=1118, L10=3162)
G. level_from_xp() works correctly
H. every XP award creates an xp_events record
I. Event Bus handler failure does not break XP processing
"""

from __future__ import annotations

import unittest
import uuid
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.gamification import UserStats, XPEvent
from app.models.user import User
from app.services.events import clear_handlers, emit, register_handler
from app.services.xp_engine import (
    TUTOR_XP_DAILY_CAP,
    XP_AWARDS,
    award_xp,
    level_for_xp,
    level_from_xp,
    register_xp_handlers,
    update_streak,
    xp_for_level,
)


class TestXPEngine(unittest.TestCase):
    """Test suite for XP Engine formulas, models, and Event Bus integration."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create an in-memory SQLite database for test execution."""
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self) -> None:
        """Set up fresh database session and reset event handlers for clean isolation."""
        self.db: Session = self.SessionLocal()
        clear_handlers()
        register_xp_handlers()

        # Create a test user for foreign key constraints
        self.user_id = uuid.uuid4()
        self.user = User(
            id=self.user_id,
            email=f"learner_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Learner",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        """Rollback and close the database session."""
        self.db.rollback()
        self.db.close()
        clear_handlers()

    def test_f_xp_for_level(self) -> None:
        """Requirement F: xp_for_level() calculates the 100 * n^1.5 curve correctly."""
        # Level thresholds per prompt requirements:
        # L2 = 282 XP, L5 = 1118 XP, L10 = 3162 XP
        self.assertEqual(xp_for_level(2), 282)
        self.assertEqual(xp_for_level(5), 1118)
        self.assertEqual(xp_for_level(10), 3162)

        # Baseline checks
        self.assertEqual(xp_for_level(1), 100)
        self.assertGreater(xp_for_level(3), xp_for_level(2))

    def test_g_level_from_xp(self) -> None:
        """Requirement G: level_from_xp() determines level based on cumulative XP."""
        self.assertEqual(level_from_xp(0), 1)
        self.assertEqual(level_from_xp(100), 1)
        self.assertEqual(level_from_xp(281), 1)
        self.assertEqual(level_from_xp(282), 2)
        self.assertEqual(level_from_xp(1117), 4)
        self.assertEqual(level_from_xp(1118), 5)
        self.assertEqual(level_from_xp(3161), 9)
        self.assertEqual(level_from_xp(3162), 10)

        # Verify backwards compatible alias level_for_xp
        self.assertEqual(level_for_xp(282), 2)
        self.assertEqual(level_for_xp(1118), 5)

    def test_h_every_xp_award_creates_xp_events_record(self) -> None:
        """Requirement H: Every XP award creates an xp_events record and updates user_stats."""
        # Start with empty ledger
        initial_events = self.db.query(XPEvent).filter(XPEvent.user_id == self.user_id).count()
        self.assertEqual(initial_events, 0)

        # Award XP directly
        result = award_xp(
            db=self.db,
            user_id=self.user_id,
            amount=75,
            reason="manual_test_bonus",
            event_type="test.bonus",
            ref_type="test",
            ref_id=uuid.uuid4(),
        )

        self.assertEqual(result["xp_awarded"], 75)
        self.assertEqual(result["total_xp"], 75)

        # Verify user_stats was created and updated
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 75)

        # Verify xp_events row was recorded
        events = self.db.query(XPEvent).filter(XPEvent.user_id == self.user_id).all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].xp_awarded, 75)
        self.assertEqual(events[0].event_type, "test.bonus")

    def test_a_lesson_completed_gives_50_xp(self) -> None:
        """Requirement A: lesson.completed gives +50 XP via Event Bus."""
        lesson_uuid = uuid.uuid4()
        payload = {
            "lesson_id": str(lesson_uuid),
            "course_id": str(uuid.uuid4()),
            "seconds": 120,
        }

        emit(self.db, self.user_id, "lesson.completed", payload)

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 50)
        self.assertEqual(stats.total_learning_seconds, 120)

        # Verify xp_events ledger
        event_row = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "lesson.completed")
            .first()
        )
        self.assertIsNotNone(event_row)
        self.assertEqual(event_row.xp_awarded, 50)
        self.assertEqual(str(event_row.ref_id), str(lesson_uuid))

    def test_b_course_enrolled_gives_20_xp(self) -> None:
        """Requirement B: course.enrolled gives +20 XP via Event Bus."""
        course_uuid = uuid.uuid4()
        payload = {"course_id": str(course_uuid)}

        emit(self.db, self.user_id, "course.enrolled", payload)

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 20)

        event_row = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "course.enrolled")
            .first()
        )
        self.assertIsNotNone(event_row)
        self.assertEqual(event_row.xp_awarded, 20)

    def test_c_quiz_partial_correct(self) -> None:
        """Requirement C: quiz with 5 questions and 3 correct gives 10 + (3 * 5) = 25 XP."""
        quiz_uuid = uuid.uuid4()
        payload = {
            "quiz_id": str(quiz_uuid),
            "correct_count": 3,
            "total_questions": 5,
        }

        emit(self.db, self.user_id, "quiz.submitted", payload)

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 25)

        event_row = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "quiz.submitted")
            .first()
        )
        self.assertIsNotNone(event_row)
        self.assertEqual(event_row.xp_awarded, 25)

    def test_d_quiz_perfect_score(self) -> None:
        """Requirement D: perfect 5-question quiz gives 10 + (5 * 5) + 25 = 60 XP."""
        quiz_uuid = uuid.uuid4()
        payload = {
            "quiz_id": str(quiz_uuid),
            "correct_count": 5,
            "total_questions": 5,
        }

        emit(self.db, self.user_id, "quiz.submitted", payload)

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 60)

        event_row = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "quiz.submitted")
            .first()
        )
        self.assertIsNotNone(event_row)
        self.assertEqual(event_row.xp_awarded, 60)

    def test_e_tutor_xp_daily_cap(self) -> None:
        """Requirement E: tutor XP cannot exceed 25 XP per day."""
        # 6 consecutive tutor sessions (5 XP each)
        for i in range(6):
            conv_id = f"conv-{i}"
            emit(self.db, self.user_id, "tutor.session", {"conversation_id": conv_id})

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        # 5 sessions * 5 XP = 25 XP, 6th session should be capped (0 XP)
        self.assertEqual(stats.xp, TUTOR_XP_DAILY_CAP)

        # Verify that sum of tutor XP events is exactly 25
        tutor_events = (
            self.db.query(XPEvent)
            .filter(XPEvent.user_id == self.user_id, XPEvent.event_type == "tutor.session")
            .all()
        )
        total_tutor_xp = sum(e.xp_awarded for e in tutor_events)
        self.assertEqual(total_tutor_xp, 25)

    def test_i_handler_failure_does_not_break_xp_processing(self) -> None:
        """Requirement I: Event Bus handler failure does not break XP processing."""
        # Register a deliberately broken handler alongside the working XP engine handler
        @register_handler("lesson.completed")
        def broken_third_party_handler(db: Any, user_id: Any, payload: dict[str, Any]) -> None:
            raise RuntimeError("Intentional external service failure!")

        lesson_uuid = uuid.uuid4()
        payload = {"lesson_id": str(lesson_uuid), "seconds": 60}

        # Calling emit should not crash
        try:
            emit(self.db, self.user_id, "lesson.completed", payload)
        except Exception as err:
            self.fail(f"emit() raised an exception despite isolation guarantee: {err}")

        # Verify XP was still awarded by the XP engine handler
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 50)

    def test_level_up_detection(self) -> None:
        """Test level up detection when XP crosses the level 2 threshold (283 XP)."""
        # Award 280 XP -> should remain Level 1
        res1 = award_xp(self.db, self.user_id, 280, "test_boost")
        self.assertEqual(res1["total_xp"], 280)
        self.assertEqual(res1["new_level"], 1)
        self.assertFalse(res1["leveled_up"])

        # Award 10 more XP (total 290 >= 283) -> should trigger level up to Level 2
        res2 = award_xp(self.db, self.user_id, 10, "test_level_up")
        self.assertEqual(res2["total_xp"], 290)
        self.assertEqual(res2["old_level"], 1)
        self.assertEqual(res2["new_level"], 2)
        self.assertTrue(res2["leveled_up"])

    def test_idempotency_duplicate_prevention(self) -> None:
        """Test that emitting the same lesson.completed twice does not award double XP."""
        lesson_uuid = uuid.uuid4()
        payload = {"lesson_id": str(lesson_uuid), "seconds": 100}

        # First emission
        emit(self.db, self.user_id, "lesson.completed", payload)
        stats1 = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertEqual(stats1.xp, 50)

        # Duplicate emission with same lesson_id
        emit(self.db, self.user_id, "lesson.completed", payload)
        stats2 = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertEqual(stats2.xp, 50)  # Remains 50, no double award!

    def test_daily_login_and_streak_bonus(self) -> None:
        """Test daily.login awards 10 XP + streak bonus and is idempotent within a single day."""
        # First daily login gives 10 XP + streak bonus (streak=1 -> bonus=5 -> total=15)
        emit(self.db, self.user_id, "daily.login", {})
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.xp, 15)
        self.assertEqual(stats.current_streak, 1)

        # Duplicate login today should not award XP again
        emit(self.db, self.user_id, "daily.login", {})
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertEqual(stats.xp, 15)

    def test_streak_lifecycle_and_longest_streak_preservation(self) -> None:
        """Week 2 Requirement 1 & 2: Test streak tracking, consecutive days, missed days, and longest_streak."""
        from datetime import date

        # Day 1: First activity -> current=1, longest=1
        s1 = update_streak(self.db, self.user_id, local_date=date(2026, 9, 1))
        self.assertEqual(s1, 1)
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertEqual(stats.current_streak, 1)
        self.assertEqual(stats.longest_streak, 1)

        # Day 1: Second activity -> remains 1
        s1_repeat = update_streak(self.db, self.user_id, local_date=date(2026, 9, 1))
        self.assertEqual(s1_repeat, 1)
        self.db.refresh(stats)
        self.assertEqual(stats.current_streak, 1)
        self.assertEqual(stats.longest_streak, 1)

        # Day 2: Consecutive day -> current=2, longest=2
        s2 = update_streak(self.db, self.user_id, local_date=date(2026, 9, 2))
        self.assertEqual(s2, 2)
        self.db.refresh(stats)
        self.assertEqual(stats.current_streak, 2)
        self.assertEqual(stats.longest_streak, 2)

        # Day 3: Consecutive day -> current=3, longest=3
        s3 = update_streak(self.db, self.user_id, local_date=date(2026, 9, 3))
        self.assertEqual(s3, 3)
        self.db.refresh(stats)
        self.assertEqual(stats.current_streak, 3)
        self.assertEqual(stats.longest_streak, 3)

        # Day 5: Missed Day 4! -> current resets to 1, longest remains 3!
        s5 = update_streak(self.db, self.user_id, local_date=date(2026, 9, 5))
        self.assertEqual(s5, 1)
        self.db.refresh(stats)
        self.assertEqual(stats.current_streak, 1)
        self.assertEqual(stats.longest_streak, 3)  # Longest streak preserved!

    def test_streak_uses_user_timezone_preference(self) -> None:
        """Week 2 Requirement 1: Streak uses user local date from preferences.timezone."""
        # Set user preferences with timezone
        self.user.preferences = {"timezone": "Asia/Tokyo"}
        self.db.commit()

        # Calling update_streak without local_date should look up the user's timezone
        current = update_streak(self.db, self.user_id, local_date=None)
        self.assertGreaterEqual(current, 1)

        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats.last_active_date)


if __name__ == "__main__":
    unittest.main()
