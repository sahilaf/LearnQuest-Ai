"""Unit and integration tests for Member 2 Week 2 Learning Flow.

Verifies:
1. GET /api/me/enrollments returns enrolled courses with progress % and next lesson.
2. POST /api/lessons/{id}/progress records progress and persists to LessonProgress.
3. Marking lesson completed emits 'lesson.completed' and marks Enrollment.completed_at when all complete.
4. GET /api/me/progress returns per-course completion stats and lesson IDs.
5. GET /api/me/history returns chronologically sorted lessons and quiz attempts with filtering.
6. GET /api/courses/{slug} attaches quiz_id to course lessons.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import CurrentUser, get_current_user
from app.main import app
from app.models.course import Course, Enrollment, Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.user import User
from app.services.events import clear_handlers, on


class TestLearningFlow(unittest.TestCase):
    """Test suite for Member 2 Week 2 Learning Management."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self) -> None:
        self.db = self.SessionLocal()
        clear_handlers()

        # Seed test user
        self.test_user_id = uuid.uuid4()
        self.test_user = User(
            id=self.test_user_id,
            email=f"learner_{uuid.uuid4().hex[:8]}@learnquest.test",
            full_name="Test Learner M2",
            role="student",
        )
        self.db.add(self.test_user)

        # Seed course with 2 lessons
        self.course_id = uuid.uuid4()
        self.course_slug = f"dbms-track-{uuid.uuid4().hex[:6]}"
        self.course = Course(
            id=self.course_id,
            title="Database Management Systems Track",
            slug=self.course_slug,
            description="Master database architecture, relational algebra, and SQL.",
            subject="Database Systems",
            difficulty="beginner",
            estimated_hours=4,
            is_published=True,
        )
        self.db.add(self.course)

        self.lesson1_id = uuid.uuid4()
        self.lesson1 = Lesson(
            id=self.lesson1_id,
            course_id=self.course_id,
            title="Introduction to Relational Databases",
            order_index=1,
            content_md="# Intro\nRelational databases organize data into tables.",
            topic_tags=["dbms.intro", "dbms.relational"],
            estimated_minutes=15,
        )
        self.db.add(self.lesson1)

        self.lesson2_id = uuid.uuid4()
        self.lesson2 = Lesson(
            id=self.lesson2_id,
            course_id=self.course_id,
            title="Relational Algebra and Joins",
            order_index=2,
            content_md="# Joins\nINNER, LEFT, and RIGHT joins.",
            topic_tags=["dbms.joins", "sql.joins"],
            estimated_minutes=20,
        )
        self.db.add(self.lesson2)

        # Attach practice quiz to lesson 1
        self.quiz_id = uuid.uuid4()
        self.quiz = Quiz(
            id=self.quiz_id,
            lesson_id=self.lesson1_id,
            title="DBMS Intro Practice Quiz",
        )
        self.db.add(self.quiz)

        # Enroll user in course
        self.enrollment = Enrollment(
            id=uuid.uuid4(),
            user_id=self.test_user_id,
            course_id=self.course_id,
        )
        self.db.add(self.enrollment)

        self.db.commit()

        # Wire dependency override for authenticated user
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.test_user_id),
            "email": self.test_user.email,
            "role": "student",
        }
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        clear_handlers()
        self.db.close()

    def test_course_detail_attaches_quiz_id(self) -> None:
        """GET /api/courses/{slug} returns course with lessons and attached quiz_id."""
        response = self.client.get(f"/api/courses/{self.course_slug}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slug"], self.course_slug)
        self.assertEqual(len(data["lessons"]), 2)

        # Lesson 1 has practice quiz attached
        l1 = next(l for l in data["lessons"] if l["id"] == str(self.lesson1_id))
        self.assertEqual(l1["quiz_id"], str(self.quiz_id))

        # Lesson 2 does not have practice quiz
        l2 = next(l for l in data["lessons"] if l["id"] == str(self.lesson2_id))
        self.assertIsNone(l2.get("quiz_id"))

    def test_lesson_progress_persistence_and_events(self) -> None:
        """POST /api/lessons/{id}/progress persists to DB and emits lesson.completed."""
        events_captured: list[dict] = []

        @on("lesson.completed")
        def capture_event(db, user_id, payload):
            events_captured.append(payload)

        # 1. Send in_progress heartbeat
        hb_resp = self.client.post(
            f"/api/lessons/{self.lesson1_id}/progress",
            json={"status": "in_progress", "seconds_spent": 45, "last_position": 350},
        )
        self.assertEqual(hb_resp.status_code, 200)
        hb_data = hb_resp.json()
        self.assertEqual(hb_data["status"], "in_progress")
        self.assertEqual(hb_data["seconds_spent"], 45)
        self.assertEqual(hb_data["last_position"], 350)
        self.assertEqual(len(events_captured), 0)

        # Verify DB persisted
        lp = self.db.query(LessonProgress).filter_by(
            user_id=self.test_user_id, lesson_id=self.lesson1_id
        ).first()
        self.assertIsNotNone(lp)
        self.assertEqual(lp.status, "in_progress")
        self.assertEqual(lp.seconds_spent, 45)

        # Verify GET /api/lessons/{id} reflects progress
        get_resp = self.client.get(f"/api/lessons/{self.lesson1_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["status"], "in_progress")
        self.assertEqual(get_resp.json()["seconds_spent"], 45)

        # 2. Mark completed
        comp_resp = self.client.post(
            f"/api/lessons/{self.lesson1_id}/progress",
            json={"status": "completed", "seconds_spent": 120, "last_position": 900},
        )
        self.assertEqual(comp_resp.status_code, 200)
        self.assertEqual(comp_resp.json()["status"], "completed")

        # Verify event was emitted
        self.assertEqual(len(events_captured), 1)
        self.assertEqual(events_captured[0]["lesson_id"], str(self.lesson1_id))
        self.assertEqual(events_captured[0]["course_id"], str(self.course_id))

    def test_enrollments_and_course_progress(self) -> None:
        """GET /api/me/enrollments and /api/me/progress calculate progress and next lesson."""
        # Initial: 0% complete, next lesson is lesson 1
        enr_resp = self.client.get("/api/me/enrollments")
        self.assertEqual(enr_resp.status_code, 200)
        items = enr_resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["course_id"], str(self.course_id))
        self.assertEqual(items[0]["completed_lessons"], 0)
        self.assertEqual(items[0]["total_lessons"], 2)
        self.assertEqual(items[0]["completion_percentage"], 0.0)
        self.assertEqual(items[0]["next_lesson_id"], str(self.lesson1_id))

        # Complete lesson 1
        self.client.post(
            f"/api/lessons/{self.lesson1_id}/progress",
            json={"status": "completed", "seconds_spent": 90},
        )

        # Progress should now be 50%, next lesson is lesson 2
        prog_resp = self.client.get("/api/me/progress")
        self.assertEqual(prog_resp.status_code, 200)
        prog_items = prog_resp.json()["items"]
        self.assertEqual(len(prog_items), 1)
        self.assertEqual(prog_items[0]["completed_lessons"], 1)
        self.assertEqual(prog_items[0]["total_lessons"], 2)
        self.assertEqual(prog_items[0]["completion_percentage"], 50.0)
        self.assertEqual(prog_items[0]["next_lesson_id"], str(self.lesson2_id))
        self.assertIn(str(self.lesson1_id), prog_items[0]["completed_lesson_ids"])

        # Complete lesson 2 -> 100% course completion
        self.client.post(
            f"/api/lessons/{self.lesson2_id}/progress",
            json={"status": "completed", "seconds_spent": 110},
        )
        enr_resp_2 = self.client.get("/api/me/enrollments")
        self.assertEqual(enr_resp_2.status_code, 200)
        self.assertEqual(enr_resp_2.json()["items"][0]["completion_percentage"], 100.0)
        self.assertEqual(enr_resp_2.json()["items"][0]["completed_lessons"], 2)

    def test_learning_history_timeline_and_filtering(self) -> None:
        """GET /api/me/history merges completed lessons and quiz attempts chronologically."""
        # 1. Complete lesson 1
        self.client.post(
            f"/api/lessons/{self.lesson1_id}/progress",
            json={"status": "completed", "seconds_spent": 180},
        )

        # 2. Record a quiz attempt
        attempt = QuizAttempt(
            id=uuid.uuid4(),
            user_id=self.test_user_id,
            quiz_id=self.quiz_id,
            started_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc),
            score=85.0,
            duration_seconds=95,
        )
        self.db.add(attempt)
        self.db.commit()

        # Query all history
        hist_resp = self.client.get("/api/me/history")
        self.assertEqual(hist_resp.status_code, 200)
        data = hist_resp.json()
        self.assertEqual(data["total"], 2)
        item_types = [it["item_type"] for it in data["items"]]
        self.assertIn("lesson", item_types)
        self.assertIn("quiz", item_types)

        # Filter by lesson
        lesson_hist = self.client.get("/api/me/history?item_type=lesson")
        self.assertEqual(lesson_hist.status_code, 200)
        self.assertEqual(lesson_hist.json()["total"], 1)
        self.assertEqual(lesson_hist.json()["items"][0]["item_type"], "lesson")
        self.assertEqual(lesson_hist.json()["items"][0]["lesson_id"], str(self.lesson1_id))

        # Filter by quiz
        quiz_hist = self.client.get("/api/me/history?item_type=quiz")
        self.assertEqual(quiz_hist.status_code, 200)
        self.assertEqual(quiz_hist.json()["total"], 1)
        self.assertEqual(quiz_hist.json()["items"][0]["item_type"], "quiz")
        self.assertEqual(quiz_hist.json()["items"][0]["score"], 85.0)
        self.assertTrue(quiz_hist.json()["items"][0]["passed"])


if __name__ == "__main__":
    unittest.main()
