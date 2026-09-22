"""Tests for Member 1 Slot 5: the G1 fix and the Teach-Back protege loop.

Covers:
1. G1 - `quiz.submitted` arriving with no `answers` list still produces a
   misconception, by reading `attempt_answers` back from the attempt.
2. Teach-Back - seed Nova, push back on a vague explanation, and grade the
   student on Nova's retake.
3. The grading guards: a wrong retake fails, and a judge that errors fails
   rather than passing by default.
"""

from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import TeachBackSession, TopicMastery
from app.models.quiz import AttemptAnswer, Question, Quiz, QuizAttempt
from app.models.user import User


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class _FakeLLM:
    """Returns a queued reply per call, so each step can be scripted."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    async def complete(self, messages, **kwargs) -> str:
        self.prompts.append(messages[0]["content"])
        if not self.replies:
            return "{}"
        return self.replies.pop(0)


class _ExplodingLLM:
    async def complete(self, messages, **kwargs) -> str:
        raise RuntimeError("provider down")


class TeachBackTestBase(unittest.TestCase):
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
        self.user_id = uuid.uuid4()
        self.db.add(
            User(
                id=self.user_id,
                email=f"{self.user_id.hex[:8]}@test.local",
                full_name="Test Learner",
            )
        )

        self.quiz = Quiz(id=uuid.uuid4(), title="SQL Joins", topic_tags=["dbms.sql_joins"])
        self.question = Question(
            id=uuid.uuid4(),
            quiz_id=self.quiz.id,
            type="mcq",
            prompt="Which join returns only rows present in both tables?",
            options=["LEFT JOIN", "INNER JOIN", "FULL OUTER JOIN"],
            correct_answer="INNER JOIN",
            topic_tag="dbms.sql_joins",
            order_index=0,
        )
        self.attempt = QuizAttempt(
            id=uuid.uuid4(),
            user_id=self.user_id,
            quiz_id=self.quiz.id,
            score=0.0,
            total_questions=1,
            correct_count=0,
            submitted_at=datetime.now(timezone.utc),
        )
        self.answer = AttemptAnswer(
            id=uuid.uuid4(),
            attempt_id=self.attempt.id,
            question_id=self.question.id,
            user_answer="FULL OUTER JOIN",
            is_correct=False,
            topic_tag="dbms.sql_joins",
        )
        self.db.add_all([self.quiz, self.question, self.attempt, self.answer])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        for model in (TeachBackSession, TopicMastery, AttemptAnswer, QuizAttempt, Question, Quiz, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()

    def _seed_misconception(self, text: str = "You believe every join keeps unmatched rows.") -> TopicMastery:
        row = TopicMastery(
            user_id=self.user_id,
            topic_tag="dbms.sql_joins",
            mastery_score=0.3,
            misconception=text,
            misconception_updated_at=datetime.now(timezone.utc),
            misconception_correct_streak=0,
            attempts=1,
            correct=0,
        )
        self.db.add(row)
        self.db.commit()
        return row


class TestG1AnswersFallback(TeachBackTestBase):
    """The payload M2 actually emits carries no `answers` list."""

    def test_loads_answers_from_attempt_when_payload_omits_them(self) -> None:
        from app.services import mastery

        fake = _FakeLLM(
            [
                json.dumps(
                    {
                        "misconception": "You believe an INNER JOIN keeps rows that match in only one table.",
                        "confidence": 0.9,
                    }
                )
            ]
        )

        # Exactly what quizzes.py:345 emits today - counts only.
        payload = {
            "quiz_id": str(self.quiz.id),
            "attempt_id": str(self.attempt.id),
            "score": 0.0,
            "correct": 0,
            "total": 1,
        }

        with patch("app.services.llm_client.get_llm", return_value=fake):
            result = mastery.handle_quiz_submitted(self.db, self.user_id, payload)

        self.assertEqual(result["topics_updated"], 1)
        self.assertEqual(result["misconceptions_captured"], 1)

        row = (
            self.db.query(TopicMastery)
            .filter(TopicMastery.user_id == self.user_id)
            .first()
        )
        self.assertIsNotNone(row)
        self.assertIn("INNER JOIN", row.misconception)

        # The prompt must have been built from the real stored answer, not a blank.
        self.assertIn("FULL OUTER JOIN", fake.prompts[0])

    def test_no_attempt_id_still_does_not_crash(self) -> None:
        from app.services import mastery

        result = mastery.handle_quiz_submitted(
            self.db, self.user_id, {"quiz_id": str(self.quiz.id), "correct": 0, "total": 1}
        )
        self.assertEqual(result["misconceptions_captured"], 0)

    def test_explicit_answers_still_win(self) -> None:
        """An emitter that does send `answers` must not be second-guessed."""
        from app.services import mastery

        fake = _FakeLLM([json.dumps({"misconception": None, "confidence": 0.1})])
        payload = {
            "attempt_id": str(self.attempt.id),
            "answers": [
                {
                    "topic_tag": "algo.recursion",
                    "prompt": "What ends a recursion?",
                    "correct_answer": "A base case",
                    "user_answer": "A loop",
                    "is_correct": False,
                }
            ],
        }
        with patch("app.services.llm_client.get_llm", return_value=fake):
            mastery.handle_quiz_submitted(self.db, self.user_id, payload)

        tags = {r.topic_tag for r in self.db.query(TopicMastery).all()}
        self.assertEqual(tags, {"algo.recursion"})


class TestTeachBackLoop(TeachBackTestBase):
    def test_start_seeds_nova_with_the_students_own_belief(self) -> None:
        from app.services import teachback

        self._seed_misconception()
        fake = _FakeLLM([json.dumps({"opening": "An INNER JOIN keeps every row from both tables, so why would this one drop any?"})])

        with patch("app.services.llm_client.get_llm", return_value=fake):
            session, error = _run(teachback.start_session(self.db, self.user_id))

        self.assertIsNone(error)
        self.assertEqual(session.status, "teaching")
        self.assertEqual(session.topic_tag, "dbms.sql_joins")
        # It reused the question the student actually got wrong.
        self.assertEqual(session.question_id, self.question.id)
        self.assertEqual(session.question_correct_answer, "INNER JOIN")
        self.assertEqual(len(session.turns), 1)
        self.assertEqual(session.turns[0]["role"], "nova")
        # Nova was told the student's belief verbatim.
        self.assertIn("unmatched rows", fake.prompts[0])

    def test_start_without_a_misconception_is_refused(self) -> None:
        from app.services import teachback

        session, error = _run(teachback.start_session(self.db, self.user_id))
        self.assertIsNone(session)
        self.assertEqual(error, "no_misconception")

    def test_vague_explanation_is_pushed_back_without_an_llm_call(self) -> None:
        from app.services import teachback

        self._seed_misconception()
        fake = _FakeLLM([json.dumps({"opening": "I think joins keep everything. Why not here?"})])
        with patch("app.services.llm_client.get_llm", return_value=fake):
            session, _ = _run(teachback.start_session(self.db, self.user_id))

        # An exploding client proves no call was made for the vague turn.
        with patch("app.services.llm_client.get_llm", return_value=_ExplodingLLM()):
            result = _run(teachback.student_turn(self.db, session, "youre wrong"))

        self.assertFalse(result["convinced"])
        self.assertFalse(result["can_retake"])
        self.assertIn("walk me through", result["reply"])

    def test_full_pass_marks_the_misconception_fading_and_awards_xp(self) -> None:
        from app.services import teachback
        from app.services.events import clear_handlers, register_handler

        row = self._seed_misconception()
        self.assertEqual(row.misconception_correct_streak, 0)

        awarded: list[dict] = []

        clear_handlers("teachback.completed")

        @register_handler("teachback.completed")
        def _capture(db, user_id, payload):  # noqa: ANN001
            awarded.append(payload)
            return {"xp_awarded": teachback.TEACHBACK_XP}

        fake = _FakeLLM(
            [
                json.dumps({"opening": "Joins keep every row, surely?"}),
                json.dumps({"reply": "Oh - so the unmatched rows are dropped.", "convinced": True}),
                json.dumps({"answer": "INNER JOIN", "reasoning": "Only matching rows survive."}),
            ]
        )

        with patch("app.services.llm_client.get_llm", return_value=fake):
            session, _ = _run(teachback.start_session(self.db, self.user_id))
            turn = _run(
                teachback.student_turn(
                    self.db,
                    session,
                    "An INNER JOIN only keeps a row when the key exists in both tables; "
                    "unmatched rows are dropped entirely rather than padded with NULLs.",
                )
            )
            self.assertTrue(turn["can_retake"])
            result = _run(teachback.retake(self.db, session))

        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 100)  # deterministic match, no judge needed
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["xp_awarded"], teachback.TEACHBACK_XP)
        self.assertEqual(result["correct_answer"], "INNER JOIN")

        self.assertEqual(len(awarded), 1)
        self.assertEqual(awarded[0]["topic_tag"], "dbms.sql_joins")

        self.db.refresh(row)
        self.assertEqual(row.misconception_correct_streak, 1)  # active -> fading
        from app.services.mastery import misconception_status

        self.assertEqual(misconception_status(row), "fading")

        clear_handlers("teachback.completed")

    def test_wrong_retake_does_not_pass_and_burns_a_retry(self) -> None:
        from app.services import teachback

        self._seed_misconception()
        fake = _FakeLLM(
            [
                json.dumps({"opening": "Joins keep every row, surely?"}),
                json.dumps({"reply": "I still do not see it.", "convinced": False}),
                json.dumps({"answer": "FULL OUTER JOIN", "reasoning": "Everything is kept."}),
            ]
        )

        with patch("app.services.llm_client.get_llm", return_value=fake):
            session, _ = _run(teachback.start_session(self.db, self.user_id))
            _run(
                teachback.student_turn(
                    self.db, session, "It is about matching keys across the two tables somehow."
                )
            )
            result = _run(teachback.retake(self.db, session))

        self.assertFalse(result["passed"])
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["status"], "teaching")  # still open, can try again
        self.assertEqual(result["retakes"], 1)
        self.assertEqual(result["retakes_left"], teachback.MAX_RETAKES - 1)
        # The answer stays hidden while the session is still winnable.
        self.assertIsNone(result["correct_answer"])

    def test_retake_before_teaching_anything_is_refused(self) -> None:
        from app.services import teachback

        self._seed_misconception()
        fake = _FakeLLM([json.dumps({"opening": "Joins keep every row, surely?"})])
        with patch("app.services.llm_client.get_llm", return_value=fake):
            session, _ = _run(teachback.start_session(self.db, self.user_id))
            result = _run(teachback.retake(self.db, session))

        self.assertEqual(result["error"], "nothing_taught")
        self.assertEqual(session.retakes, 0)


class TestGradingGuards(TeachBackTestBase):
    def test_deterministic_match_picks_the_single_named_option(self) -> None:
        from app.services.teachback import _deterministic_match

        options = ["LEFT JOIN", "INNER JOIN", "FULL OUTER JOIN"]
        self.assertTrue(_deterministic_match("INNER JOIN", "INNER JOIN", options))
        self.assertTrue(
            _deterministic_match("It would be an INNER JOIN here.", "INNER JOIN", options)
        )
        self.assertFalse(_deterministic_match("LEFT JOIN", "INNER JOIN", options))
        # Naming several options is not an answer - defer, do not pass.
        self.assertIsNone(
            _deterministic_match("either LEFT JOIN or INNER JOIN", "INNER JOIN", options)
        )

    def test_judge_failure_fails_the_retake_rather_than_passing(self) -> None:
        from app.services.teachback import _grade

        with patch("app.services.llm_client.get_llm", return_value=_ExplodingLLM()):
            result = _run(_grade("Explain a join", "a specific technical phrase", "something else entirely", None))

        self.assertFalse(result["correct"])
        self.assertEqual(result["score"], 0)

    def test_judge_cannot_pass_with_a_contradictory_score(self) -> None:
        from app.services.teachback import PASS_SCORE, _grade

        fake = _FakeLLM([json.dumps({"correct": True, "score": 20, "why": "sort of"})])
        with patch("app.services.llm_client.get_llm", return_value=fake):
            result = _run(_grade("Q", "a specific technical phrase", "unrelated words here", None))

        self.assertFalse(result["correct"])
        self.assertLess(result["score"], PASS_SCORE)


class TestTeachBackAPI(TeachBackTestBase):
    """The HTTP surface: routing, auth wiring and what the client is told."""

    def setUp(self) -> None:
        super().setUp()
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id),
            "email": "test@local",
            "role": "student",
        }
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        super().tearDown()

    def test_full_round_trip(self) -> None:
        from app.models.gamification import UserStats
        from app.services.mastery import misconception_status

        self._seed_misconception()
        fake = _FakeLLM(
            [
                json.dumps({"opening": "Joins keep every row, surely?"}),
                json.dumps({"reply": "Ah - so unmatched rows vanish.", "convinced": True}),
                json.dumps({"answer": "INNER JOIN", "reasoning": "Only matching rows survive."}),
            ]
        )

        with patch("app.services.llm_client.get_llm", return_value=fake):
            listed = self.client.get("/api/tutor/teachback/available")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["total"], 1)

            started = self.client.post("/api/tutor/teachback/start", json={})
            self.assertEqual(started.status_code, 201)
            session = started.json()
            # The thing being taught must not be handed to the client.
            self.assertNotIn("question_correct_answer", session)

            taught = self.client.post(
                f"/api/tutor/teachback/{session['id']}/teach",
                json={
                    "message": "An INNER JOIN only keeps rows whose key exists in "
                    "both tables; unmatched rows are dropped."
                },
            )
            self.assertEqual(taught.status_code, 200)
            self.assertIn("reply", taught.json())

            done = self.client.post(f"/api/tutor/teachback/{session['id']}/retake")

        self.assertEqual(done.status_code, 200)
        body = done.json()
        self.assertTrue(body["passed"])
        self.assertEqual(body["xp_awarded"], 40)
        # Released only now that the session is over.
        self.assertEqual(body["correct_answer"], "INNER JOIN")

        row = self.db.query(TopicMastery).filter(TopicMastery.user_id == self.user_id).first()
        self.assertEqual(misconception_status(row), "fading")

        # XP went through Member 4's engine, so the audited stats row moved.
        stats = self.db.query(UserStats).filter(UserStats.user_id == self.user_id).first()
        self.assertEqual(stats.xp, 40)

    def test_start_with_nothing_to_teach_is_a_404(self) -> None:
        response = self.client.post("/api/tutor/teachback/start", json={})
        self.assertEqual(response.status_code, 404)

    def test_another_users_session_is_not_readable(self) -> None:
        from app.models.ai import TeachBackSession

        stranger = TeachBackSession(
            user_id=uuid.uuid4(),
            topic_tag="dbms.sql_joins",
            misconception="Someone else's belief.",
            question_prompt="Q",
            question_correct_answer="A",
            status="teaching",
            turns=[],
        )
        self.db.add(stranger)
        self.db.commit()

        response = self.client.get(f"/api/tutor/teachback/{stranger.id}")
        self.assertEqual(response.status_code, 404)


class TestConversationNumbers(TeachBackTestBase):
    """Tutor URLs address a conversation by a per-user number, not its UUID."""

    def setUp(self) -> None:
        super().setUp()
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id),
            "email": "test@local",
            "role": "student",
        }
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        from app.models.ai import Conversation

        self.app.dependency_overrides.clear()
        self.db.query(Conversation).delete()
        self.db.commit()
        super().tearDown()

    def test_numbers_start_at_one_and_increment(self) -> None:
        first = self.client.post("/api/tutor/conversations", json={"title": "One"})
        second = self.client.post("/api/tutor/conversations", json={"title": "Two"})

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["number"], 1)
        self.assertEqual(second.json()["number"], 2)

    def test_fetchable_by_number_and_by_uuid(self) -> None:
        """Old links are UUIDs, so both forms have to resolve."""
        created = self.client.post("/api/tutor/conversations", json={"title": "Joins"}).json()

        by_number = self.client.get(f"/api/tutor/conversations/{created['number']}")
        by_uuid = self.client.get(f"/api/tutor/conversations/{created['id']}")

        self.assertEqual(by_number.status_code, 200)
        self.assertEqual(by_uuid.status_code, 200)
        self.assertEqual(by_number.json()["id"], by_uuid.json()["id"])

    def test_numbers_are_scoped_to_the_user(self) -> None:
        """Another user's number 1 must not be reachable as ours."""
        from app.models.ai import Conversation
        from app.models.user import User

        stranger_id = uuid.uuid4()
        self.db.add(User(id=stranger_id, email="other@test.local", full_name="Other"))
        self.db.add(
            Conversation(
                id=uuid.uuid4(),
                user_id=stranger_id,
                number=1,
                title="Not yours",
            )
        )
        self.db.commit()

        # We have no conversations at all, so our number 1 does not exist.
        response = self.client.get("/api/tutor/conversations/1")
        self.assertEqual(response.status_code, 404)

    def test_unparseable_reference_is_a_404_not_a_500(self) -> None:
        response = self.client.get("/api/tutor/conversations/not-a-real-id")
        self.assertEqual(response.status_code, 404)


class TestDemoIntegrity(TeachBackTestBase):
    """The two rules that make the retake a measurement rather than a formality."""

    def test_reciting_the_answer_does_not_count_as_teaching(self) -> None:
        """An examiner will type the answer at Nova. It must not score."""
        from app.services.teachback import _answer_was_handed_over

        answer = "Only rows that have matching values in both tables"

        self.assertTrue(
            _answer_was_handed_over([f"No. The answer is: {answer}."], answer)
        )
        self.assertTrue(_answer_was_handed_over([answer], answer))

        # A real explanation that happens to quote the answer still counts as
        # teaching - it is the absence of anything else that gives a parrot away.
        explanation = (
            f"{answer} because the database walks each row on the left, looks for "
            "a partner using the join condition, and discards any row that has no "
            "partner rather than padding it with nulls, which is exactly what "
            "separates this from an outer join in practice"
        )
        self.assertFalse(_answer_was_handed_over([explanation], answer))

        # Never fires when the answer was not mentioned at all.
        self.assertFalse(
            _answer_was_handed_over(["unmatched rows get dropped"], answer)
        )

    def test_a_wrong_answer_blocks_the_decay_for_that_topic(self) -> None:
        """Three right and one wrong on one topic must not clear the belief.

        This is what silently broke the demo: a four-question quiz on a single
        topic ran the decay three times off the questions the learner got right
        and cleared the misconception the fourth had just revealed.
        """
        from app.services import mastery
        from app.services.mastery import misconception_status

        row = self._seed_misconception()
        row.misconception_correct_streak = 1  # already fading
        self.db.commit()

        fake = _FakeLLM(
            [json.dumps({"misconception": None, "confidence": 0.1})]  # capture abstains
        )
        payload = {
            "answers": [
                {"topic_tag": "dbms.sql_joins", "prompt": "q1", "correct_answer": "a",
                 "user_answer": "a", "is_correct": True},
                {"topic_tag": "dbms.sql_joins", "prompt": "q2", "correct_answer": "b",
                 "user_answer": "b", "is_correct": True},
                {"topic_tag": "dbms.sql_joins", "prompt": "q3", "correct_answer": "c",
                 "user_answer": "wrong", "is_correct": False},
            ]
        }

        with patch("app.services.llm_client.get_llm", return_value=fake):
            mastery.handle_quiz_submitted(self.db, self.user_id, payload)

        self.db.refresh(row)
        # Still fading, not cleared: they got one wrong on this very topic, and
        # even though the capture call abstained the belief must survive.
        self.assertEqual(row.misconception_correct_streak, 1)
        self.assertIsNone(row.misconception_cleared_at)
        self.assertEqual(misconception_status(row), "fading")

    def test_a_clean_sweep_still_decays(self) -> None:
        """The guard must not stop a genuinely correct topic from clearing."""
        from app.services import mastery
        from app.services.mastery import misconception_status

        row = self._seed_misconception()
        payload = {
            "answers": [
                {"topic_tag": "dbms.sql_joins", "prompt": "q1", "correct_answer": "a",
                 "user_answer": "a", "is_correct": True},
            ]
        }
        mastery.handle_quiz_submitted(self.db, self.user_id, payload)

        self.db.refresh(row)
        self.assertEqual(row.misconception_correct_streak, 1)
        self.assertEqual(misconception_status(row), "fading")


if __name__ == "__main__":
    unittest.main()
