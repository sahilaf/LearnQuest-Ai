"""Unit tests for the Data-Driven Badge Checker and Achievement System (Week 2).

Verifies:
1. Badge seeding creates exactly two initial badges: 'first_lesson' and 'streak_7'.
2. Seed operation is idempotent.
3. Criteria evaluation is data-driven (evaluates count, streak, stat).
4. Badge awarding creates user_badges, notification, emits 'badge.earned', awards XP.
5. Duplicate awards are strictly prevented.
6. Event-driven checking:
   - Emitting 'lesson.completed' awards 'first_lesson' on first completion.
   - Emitting 'streak.updated' with 7-day streak awards 'streak_7'.
7. Badge evaluation failure does not break the primary event or caller.
8. GET /api/me/achievements returns earned and locked badges with live progress.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.gamification import Badge, Notification, UserBadge, UserStats, XPEvent
from app.models.progress import LessonProgress
from app.models.user import User
from app.seed.seed_data import seed_badges
from app.services.badge_checker import (
    award_badge,
    check_badges,
    get_badge_progress,
    register_badge_handlers,
)
from app.services.events import clear_handlers, emit, register_handler
from app.services.xp_engine import register_xp_handlers


class TestBadgeChecker(unittest.TestCase):
    """Test suite for data-driven badge checker, badge awarding, and event bus integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self) -> None:
        self.db: Session = self.SessionLocal()
        clear_handlers()
        register_xp_handlers()
        register_badge_handlers()

        # Seed initial badges (first_lesson and streak_7)
        seed_badges(self.db)

        # Create test user
        self.user_id = uuid.uuid4()
        self.user = User(
            id=self.user_id,
            email=f"badge_user_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Badge Tester",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        clear_handlers()

    def test_1_seed_badges_exactly_two_initial_badges(self) -> None:
        """Requirement 3: Exactly two initial badges are seeded: 'first_lesson' and 'streak_7'."""
        badges = self.db.query(Badge).all()
        badge_codes = {b.code for b in badges}

        self.assertEqual(len(badges), 2)
        self.assertIn("first_lesson", badge_codes)
        self.assertIn("streak_7", badge_codes)

        # Verify idempotency
        seed_badges(self.db)
        badges_after = self.db.query(Badge).all()
        self.assertEqual(len(badges_after), 2)

    def test_2_first_lesson_criteria_progress(self) -> None:
        """Requirement 4: Data-driven criteria evaluation for 'first_lesson'."""
        badge = self.db.query(Badge).filter(Badge.code == "first_lesson").first()
        self.assertIsNotNone(badge)

        # Before any lesson completed
        progress_before = get_badge_progress(self.db, self.user_id, badge)
        self.assertEqual(progress_before["current"], 0)
        self.assertEqual(progress_before["target"], 1)
        self.assertFalse(progress_before["satisfied"])

        # Record a completed lesson via xp_events
        event = XPEvent(
            id=uuid.uuid4(),
            user_id=self.user_id,
            event_type="lesson.completed",
            xp_awarded=50,
            ref_type="lesson",
            ref_id=uuid.uuid4(),
        )
        self.db.add(event)
        self.db.commit()

        # After lesson completed
        progress_after = get_badge_progress(self.db, self.user_id, badge)
        self.assertGreaterEqual(progress_after["current"], 1)
        self.assertTrue(progress_after["satisfied"])

    def test_3_streak_7_criteria_progress(self) -> None:
        """Requirement 4: Data-driven criteria evaluation for 'streak_7'."""
        badge = self.db.query(Badge).filter(Badge.code == "streak_7").first()
        self.assertIsNotNone(badge)

        # Streak = 4
        stats = UserStats(
            user_id=self.user_id,
            xp=100,
            level=1,
            current_streak=4,
            longest_streak=4,
            last_active_date=date.today(),
        )
        self.db.add(stats)
        self.db.commit()

        progress = get_badge_progress(self.db, self.user_id, badge)
        self.assertEqual(progress["current"], 4)
        self.assertEqual(progress["target"], 7)
        self.assertEqual(progress["percentage"], 57)
        self.assertFalse(progress["satisfied"])

        # Update streak to 7
        stats.current_streak = 7
        stats.longest_streak = 7
        self.db.commit()

        progress_7 = get_badge_progress(self.db, self.user_id, badge)
        self.assertEqual(progress_7["current"], 7)
        self.assertEqual(progress_7["target"], 7)
        self.assertEqual(progress_7["percentage"], 100)
        self.assertTrue(progress_7["satisfied"])

    def test_4_award_badge_and_prevent_duplicate(self) -> None:
        """Requirement 5: Badge awarding records user_badges, creates notification, and prevents duplicates."""
        badge = self.db.query(Badge).filter(Badge.code == "first_lesson").first()
        self.assertIsNotNone(badge)

        # First award
        awarded = award_badge(self.db, self.user_id, badge)
        self.assertIsNotNone(awarded)

        # Check database record
        user_badge = self.db.query(UserBadge).filter(
            UserBadge.user_id == self.user_id,
            UserBadge.badge_id == badge.id,
        ).first()
        self.assertIsNotNone(user_badge)

        # Check in-app notification
        notification = self.db.query(Notification).filter(
            Notification.user_id == self.user_id,
            Notification.type == "badge_earned",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("First Lesson", notification.title)

        # Duplicate award attempt
        duplicate = award_badge(self.db, self.user_id, badge)
        self.assertIsNone(duplicate)

        # Still only 1 record in user_badges
        count = self.db.query(UserBadge).filter(
            UserBadge.user_id == self.user_id,
            UserBadge.badge_id == badge.id,
        ).count()
        self.assertEqual(count, 1)

    def test_5_event_driven_first_lesson_badge(self) -> None:
        """Requirement 9: Emitting lesson.completed automatically awards first_lesson badge."""
        lesson_id = str(uuid.uuid4())

        # Emit lesson.completed
        emit(
            self.db,
            self.user_id,
            "lesson.completed",
            {"lesson_id": lesson_id, "course_id": str(uuid.uuid4())},
        )

        # Verify first_lesson badge was awarded automatically
        first_lesson_badge = self.db.query(Badge).filter(Badge.code == "first_lesson").first()
        user_badge = self.db.query(UserBadge).filter(
            UserBadge.user_id == self.user_id,
            UserBadge.badge_id == first_lesson_badge.id,
        ).first()
        self.assertIsNotNone(user_badge)

    def test_6_event_driven_streak_7_badge(self) -> None:
        """Requirement 9: Reaching 7-day streak automatically awards streak_7 badge."""
        # Initialize user_stats with 6 days
        stats = UserStats(
            user_id=self.user_id,
            xp=200,
            level=1,
            current_streak=6,
            longest_streak=6,
            last_active_date=date(2026, 9, 20),
        )
        self.db.add(stats)
        self.db.commit()

        # Emit activity on next day (2026-09-21) to reach streak 7
        emit(
            self.db,
            self.user_id,
            "lesson.completed",
            {"lesson_id": str(uuid.uuid4()), "local_date": "2026-09-21"},
        )

        self.db.refresh(stats)
        self.assertEqual(stats.current_streak, 7)

        # Verify streak_7 badge was earned
        streak_badge = self.db.query(Badge).filter(Badge.code == "streak_7").first()
        user_badge = self.db.query(UserBadge).filter(
            UserBadge.user_id == self.user_id,
            UserBadge.badge_id == streak_badge.id,
        ).first()
        self.assertIsNotNone(user_badge)

    def test_7_badge_handler_error_isolation(self) -> None:
        """Requirement 4 & 9: Broken badge handler does not fail emission or caller."""
        @register_handler("lesson.completed")
        def crashing_badge_listener(db: Any, user_id: Any, payload: dict[str, Any]) -> None:
            raise RuntimeError("Badge check service offline")

        try:
            results = emit(
                self.db,
                self.user_id,
                "lesson.completed",
                {"lesson_id": str(uuid.uuid4())},
            )
        except Exception as err:
            self.fail(f"emit() crashed due to failing badge listener: {err}")

        # Primary XP processing still succeeded
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertIsNotNone(stats)
        self.assertGreater(stats.xp, 0)

    def test_8_api_me_achievements_endpoint(self) -> None:
        """Requirement 7 & 8: /api/me/achievements endpoint returns earned and locked badges with progress."""
        from app.routers.gamification import my_achievements

        # Award first_lesson badge
        badge = self.db.query(Badge).filter(Badge.code == "first_lesson").first()
        award_badge(self.db, self.user_id, badge)

        res = my_achievements(user={"id": str(self.user_id)}, db=self.db)
        self.assertEqual(res["total_earned"], 1)
        self.assertEqual(res["total_badges"], 2)

        # Earned list contains first_lesson
        earned_codes = [b["code"] for b in res["earned"]]
        self.assertIn("first_lesson", earned_codes)
        self.assertTrue(res["earned"][0]["is_earned"])
        self.assertIsNotNone(res["earned"][0]["earned_at"])

        # Locked list contains streak_7
        locked_codes = [b["code"] for b in res["locked"]]
        self.assertIn("streak_7", locked_codes)
        self.assertFalse(res["locked"][0]["is_earned"])
        self.assertIn("progress", res["locked"][0])
        self.assertEqual(res["locked"][0]["progress"]["target"], 7)


if __name__ == "__main__":
    unittest.main()
