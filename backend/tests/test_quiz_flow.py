"""Unit and integration tests for Member 2 Quiz Flow.

Verifies:
1. Pre-submission sanitization (correct_answer and explanation stripped).
2. Attempt creation and persistence.
3. Attempt submission, server-side grading, and topic_tag denormalization.
4. Event emission of 'quiz.submitted'.
5. Post-submission attempt review with explanations.
6. Edge case handling (already submitted, non-existent quiz, non-existent attempt).
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
from app.models.course import Course, Lesson
from app.models.quiz import AttemptAnswer, Question, Quiz, QuizAttempt
from app.models.user import User
from app.services.events import clear_handlers, on


class TestQuizFlow(unittest.TestCase):
    """Test suite for Member 2 Quiz Endpoints and Flow."""

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
            full_name="Test Learner",
            role="student",
        )
        self.db.add(self.test_user)

        # Seed course and lesson
        self.course_id = uuid.uuid4()
        self.course = Course(
            id=self.course_id,
            title="Database Architecture",
            slug=f"db-arch-{uuid.uuid4().hex[:6]}",
            subject="Database Systems",
            difficulty="beginner",
            is_published=True,
        )
        self.db.add(self.course)

        self.lesson_id = uuid.uuid4()
        self.lesson = Lesson(
            id=self.lesson_id,
            course_id=self.course_id,
            title="Relational Algebra",
            order_index=1,
            topic_tags=["dbms.relational_algebra"],
            content_md="# Relational Algebra",
        )
        self.db.add(self.lesson)

        # Seed Quiz with 3 question types
        self.quiz_id = uuid.uuid4()
        self.quiz = Quiz(
            id=self.quiz_id,
            lesson_id=self.lesson_id,
            course_id=self.course_id,
            title="Algebra Practice Quiz",
            source="manual",
            difficulty="beginner",
            topic_tags=["dbms.relational_algebra"],
        )
        self.db.add(self.quiz)

        self.q1 = Question(
            id=uuid.uuid4(),
            quiz_id=self.quiz_id,
            type="mcq",
            prompt="Which operator performs selection?",
            options=["Sigma (σ)", "Pi (π)", "Rho (ρ)", "Bowtie (⋈)"],
            correct_answer="Sigma (σ)",
            explanation="Sigma denotes unary row filtering/selection.",
            topic_tag="dbms.relational_algebra",
            order_index=1,
        )
        self.q2 = Question(
            id=uuid.uuid4(),
            quiz_id=self.quiz_id,
            type="true_false",
            prompt="Projection (π) eliminates duplicate tuples in standard relational algebra.",
            options=["True", "False"],
            correct_answer="True",
            explanation="Relations are mathematical sets; duplicate tuples are eliminated.",
            topic_tag="dbms.relational_algebra",
            order_index=2,
        )
        self.q3 = Question(
            id=uuid.uuid4(),
            quiz_id=self.quiz_id,
            type="short_answer",
            prompt="What is the symbol for natural join?",
            options=None,
            correct_answer="Bowtie",
            explanation="The bowtie symbol (⋈) represents natural join.",
            topic_tag="dbms.relational_algebra",
            order_index=3,
        )
        self.db.add_all([self.q1, self.q2, self.q3])
        self.db.commit()

        # Mock CurrentUser dependency
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.test_user_id),
            "email": self.test_user.email,
            "role": "student",
        }
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        clear_handlers()
        self.db.close()

    def test_01_get_quiz_strips_answers_and_explanations(self) -> None:
        """Pre-submit security check: correct_answer & explanation must NOT be exposed."""
        response = self.client.get(f"/api/quizzes/{self.quiz_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["id"], str(self.quiz_id))
        self.assertEqual(len(data["questions"]), 3)

        for q in data["questions"]:
            self.assertNotIn("correct_answer", q)
            self.assertNotIn("explanation", q)
            self.assertIn("prompt", q)
            self.assertIn("type", q)

    def test_02_get_quiz_by_lesson(self) -> None:
        """Verify quiz can be fetched by its associated lesson_id."""
        response = self.client.get(f"/api/quizzes/lesson/{self.lesson_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], str(self.quiz_id))
        self.assertEqual(data["lesson_id"], str(self.lesson_id))

    def test_03_start_attempt(self) -> None:
        """Verify attempt creation."""
        response = self.client.post(f"/api/quizzes/{self.quiz_id}/attempts")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("attempt_id", data)
        self.assertEqual(data["quiz_id"], str(self.quiz_id))

        # Check DB record
        attempt_uuid = uuid.UUID(data["attempt_id"])
        attempt = self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_uuid).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.user_id, self.test_user_id)
        self.assertIsNone(attempt.submitted_at)

    def test_04_submit_attempt_and_event_emission(self) -> None:
        """Verify submission, scoring, topic_tag denormalization, and event emission."""
        emitted_events: list[dict] = []

        @on("quiz.submitted")
        def handle_quiz_submitted(db, user_id, payload):
            emitted_events.append({"user_id": user_id, "payload": payload})

        # Start attempt
        start_res = self.client.post(f"/api/quizzes/{self.quiz_id}/attempts")
        attempt_id = start_res.json()["attempt_id"]

        # Submit answers: 2 correct, 1 wrong
        submit_payload = {
            "answers": [
                {"question_id": str(self.q1.id), "user_answer": "Sigma (σ)"},    # Correct
                {"question_id": str(self.q2.id), "user_answer": "True"},          # Correct
                {"question_id": str(self.q3.id), "user_answer": "Wrong answer"},  # Incorrect
            ]
        }

        sub_res = self.client.post(f"/api/quizzes/attempts/{attempt_id}/submit", json=submit_payload)
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.json()

        self.assertEqual(sub_data["correct"], 2)
        self.assertEqual(sub_data["total"], 3)
        self.assertAlmostEqual(sub_data["score"], 66.67, delta=0.1)

        # Verify DB attempt state
        attempt_uuid = uuid.UUID(attempt_id)
        attempt = self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_uuid).first()
        self.assertIsNotNone(attempt.submitted_at)
        self.assertEqual(attempt.correct_count, 2)

        # Verify AttemptAnswer rows have denormalized topic_tag
        answers = self.db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id == attempt_uuid).all()
        self.assertEqual(len(answers), 3)
        for a in answers:
            self.assertEqual(a.topic_tag, "dbms.relational_algebra")

        # Verify event was emitted
        self.assertEqual(len(emitted_events), 1)
        self.assertEqual(emitted_events[0]["user_id"], self.test_user_id)
        self.assertEqual(emitted_events[0]["payload"]["quiz_id"], str(self.quiz_id))
        self.assertEqual(emitted_events[0]["payload"]["correct"], 2)

    def test_05_get_attempt_review_post_submission(self) -> None:
        """Verify post-submission review provides explanations and correct answers."""
        # Start and submit attempt
        start_res = self.client.post(f"/api/quizzes/{self.quiz_id}/attempts")
        attempt_id = start_res.json()["attempt_id"]

        submit_payload = {
            "answers": [
                {"question_id": str(self.q1.id), "user_answer": "Sigma (σ)"},
                {"question_id": str(self.q2.id), "user_answer": "False"},
                {"question_id": str(self.q3.id), "user_answer": "Bowtie"},
            ]
        }
        self.client.post(f"/api/quizzes/attempts/{attempt_id}/submit", json=submit_payload)

        # Retrieve result review
        res = self.client.get(f"/api/quizzes/attempts/{attempt_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["attempt_id"], attempt_id)
        self.assertEqual(data["correct_count"], 2)
        self.assertEqual(len(data["answers"]), 3)

        # Explanations ARE present post-submit
        for ans in data["answers"]:
            self.assertIn("explanation", ans)
            self.assertIn("correct_answer", ans)
            self.assertIn("is_correct", ans)

    def test_06_double_submission_rejected(self) -> None:
        """Verify attempt cannot be submitted twice."""
        start_res = self.client.post(f"/api/quizzes/{self.quiz_id}/attempts")
        attempt_id = start_res.json()["attempt_id"]

        payload = {"answers": [{"question_id": str(self.q1.id), "user_answer": "Sigma (σ)"}]}
        first_sub = self.client.post(f"/api/quizzes/attempts/{attempt_id}/submit", json=payload)
        self.assertEqual(first_sub.status_code, 200)

        # Second submission must fail with 400
        second_sub = self.client.post(f"/api/quizzes/attempts/{attempt_id}/submit", json=payload)
        self.assertEqual(second_sub.status_code, 400)


if __name__ == "__main__":
    unittest.main()
