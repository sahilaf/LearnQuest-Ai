"""Review queue, free-text grading and recommendations.

The grading tests matter most. The Review screen used to fall back to a client
that marked any answer over three characters correct and attached the same
hardcoded misconception to every wrong one. The rules below are what replaced
it: empty is wrong, an unsure or inconsistent judge abstains rather than
guessing, and "correct" is never taken on a model's word alone.
"""

from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import Recommendation, ReviewItem, Topic, TopicMastery
from app.models.course import Course, Enrollment, Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Question, Quiz
from app.models.user import User
from app.services import open_grader, recommender, scheduler


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        return self.reply


class _DeadLLM:
    async def complete(self, messages, **kwargs):
        raise RuntimeError("provider down")


def _judge(verdict, score, confidence, feedback="Good reasoning."):
    return _FakeLLM(json.dumps(
        {"verdict": verdict, "score": score, "confidence": confidence, "feedback": feedback}
    ))


# --------------------------------------------------------------------------- #
# Free-text grading
# --------------------------------------------------------------------------- #

class TestOpenGrader(unittest.TestCase):
    def _grade(self, llm, given="some answer that needs judging"):
        with patch("app.services.llm_client.get_llm", return_value=llm):
            return _run(open_grader.grade_open("Q?", "a specific expected idea", given))

    def test_an_empty_answer_is_wrong_without_asking_anyone(self) -> None:
        llm = _judge("correct", 1.0, 1.0)
        with patch("app.services.llm_client.get_llm", return_value=llm):
            r = _run(open_grader.grade_open("Q?", "x", "   "))
        self.assertFalse(r["is_correct"])
        self.assertEqual(llm.calls, 0)

    def test_three_characters_is_not_automatically_right(self) -> None:
        """The old fallback passed anything over three characters."""
        r = self._grade(_judge("incorrect", 0.1, 0.9), given="asdf")
        self.assertFalse(r["is_correct"])

    def test_containing_the_expected_answer_needs_no_model(self) -> None:
        llm = _judge("incorrect", 0.0, 1.0)
        with patch("app.services.llm_client.get_llm", return_value=llm):
            r = _run(open_grader.grade_open("Q?", "only matching rows", "It keeps only matching rows."))
        self.assertTrue(r["is_correct"])
        self.assertEqual(llm.calls, 0)

    def test_a_confident_consistent_judge_is_accepted(self) -> None:
        r = self._grade(_judge("correct", 0.9, 0.9))
        self.assertTrue(r["is_correct"])
        self.assertEqual(r["graded_by"], "model")

    def test_a_dead_judge_abstains_rather_than_passing(self) -> None:
        r = self._grade(_DeadLLM())
        self.assertFalse(r["is_correct"])
        self.assertTrue(r["needs_review"])

    def test_an_unsure_judge_abstains(self) -> None:
        r = self._grade(_judge("correct", 0.95, 0.3))
        self.assertFalse(r["is_correct"])
        self.assertTrue(r["needs_review"])

    def test_a_contradictory_judge_is_read_conservatively(self) -> None:
        """"correct" with a score of 0.2 means it has not decided."""
        r = self._grade(_judge("correct", 0.2, 0.9))
        self.assertFalse(r["is_correct"])

    def test_choices_compare_exactly(self) -> None:
        self.assertTrue(open_grader.grade_choice("INNER JOIN", "inner join")["is_correct"])
        self.assertFalse(open_grader.grade_choice("LEFT JOIN", "INNER JOIN")["is_correct"])
        self.assertFalse(open_grader.grade_choice("", "INNER JOIN")["is_correct"])


# --------------------------------------------------------------------------- #
# Scheduling
# --------------------------------------------------------------------------- #

class TestScheduling(unittest.TestCase):
    def test_intervals_follow_sm2_lite(self) -> None:
        self.assertEqual(scheduler.next_interval(1, True), 2)
        self.assertEqual(scheduler.next_interval(4, True), 10)
        self.assertEqual(scheduler.next_interval(40, True), scheduler.MAX_INTERVAL_DAYS)
        self.assertEqual(scheduler.next_interval(30, False), scheduler.WRONG_INTERVAL_DAYS)

    def test_interleaving_never_repeats_a_topic_back_to_back(self) -> None:
        class I:
            def __init__(self, tag):
                self.topic_tag = tag

        order = [i.topic_tag for i in scheduler.interleave(
            [I("a"), I("a"), I("a"), I("b"), I("b"), I("c")]
        )]
        self.assertEqual(sorted(order), ["a", "a", "a", "b", "b", "c"])
        for first, second in zip(order, order[1:3]):
            self.assertNotEqual(first, second)


class _DBCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self) -> None:
        self.db = self.Session()
        self.user_id = uuid.uuid4()
        self.db.add(User(id=self.user_id, email=f"{self.user_id.hex[:8]}@t.local", full_name="T"))
        for tag, label in (("dbms.sql_joins", "SQL joins"), ("dbms.er_model", "ER model")):
            self.db.add(Topic(tag=tag, label=label, subject="dbms", is_active=True))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        for model in (
            Recommendation, ReviewItem, LessonProgress, Enrollment, Question, Quiz,
            Lesson, Course, TopicMastery, Topic, User,
        ):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()


class TestReviewQueue(_DBCase):
    def _bank(self, tag="dbms.sql_joins", qtype="mcq"):
        quiz = Quiz(id=uuid.uuid4(), title="bank", topic_tags=[tag])
        self.db.add(quiz)
        self.db.flush()
        q = Question(
            id=uuid.uuid4(), quiz_id=quiz.id, type=qtype,
            prompt="Which join keeps only matching rows?",
            options=["INNER JOIN", "LEFT JOIN"] if qtype == "mcq" else None,
            correct_answer="INNER JOIN", topic_tag=tag, order_index=0,
        )
        self.db.add(q)
        self.db.commit()
        return q

    def test_enrolling_twice_does_not_reset_earned_progress(self) -> None:
        item = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
        item.interval_days = 10
        self.db.commit()
        again = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
        self.assertEqual(again.id, item.id)
        self.assertEqual(again.interval_days, 10)

    def test_one_topic_is_one_item_whatever_enrolled_it(self) -> None:
        """Upload (with lesson) then quiz (without) made two items - 2026-09-29."""
        course = Course(id=uuid.uuid4(), title="C", slug=f"c-{uuid.uuid4().hex[:6]}")
        self.db.add(course)
        self.db.flush()
        lesson = Lesson(id=uuid.uuid4(), course_id=course.id, title="L", order_index=0,
                        content_md="x", topic_tags=["dbms.sql_joins"])
        self.db.add(lesson)
        self.db.flush()
        first = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins", source_lesson_id=lesson.id)
        second = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(ReviewItem).count(), 1)

    def test_existing_duplicates_are_merged_keeping_progress(self) -> None:
        """The live case: the lesson is on the item being dropped, and
        uq_review_items_user_topic_lesson rejected moving it before the delete."""
        self._bank()
        course = Course(id=uuid.uuid4(), title="C", slug=f"c-{uuid.uuid4().hex[:6]}")
        self.db.add(course)
        self.db.flush()
        lesson = Lesson(id=uuid.uuid4(), course_id=course.id, title="L", order_index=0,
                        content_md="x", topic_tags=["dbms.sql_joins"])
        self.db.add(lesson)
        self.db.flush()
        now = datetime.now(timezone.utc)
        self.db.add_all([
            ReviewItem(user_id=self.user_id, topic_tag="dbms.sql_joins", due_at=now,
                       interval_days=1, streak=0, source_lesson_id=lesson.id),
            ReviewItem(user_id=self.user_id, topic_tag="dbms.sql_joins", due_at=now,
                       interval_days=5, streak=2),
        ])
        self.db.commit()
        items = _run(scheduler.due_items(self.db, self.user_id))
        self.assertEqual(len(items), 1)
        kept = self.db.query(ReviewItem).one()
        self.assertEqual((kept.interval_days, kept.streak), (5, 2))
        self.assertEqual(kept.source_lesson_id, lesson.id)

    def test_another_students_generated_questions_are_never_used(self) -> None:
        stranger = uuid.uuid4()
        quiz = Quiz(id=uuid.uuid4(), title="theirs", topic_tags=["dbms.er_model"],
                    source="ai_generated", generated_by_user=stranger)
        self.db.add(quiz)
        self.db.flush()
        self.db.add(Question(id=uuid.uuid4(), quiz_id=quiz.id, type="mcq", prompt="Their private question?",
                             options=["a", "b"], correct_answer="a", topic_tag="dbms.er_model", order_index=0))
        scheduler.enrol_topic(self.db, self.user_id, "dbms.er_model")
        self.db.commit()
        with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
            items = _run(scheduler.due_items(self.db, self.user_id))
        self.assertEqual(items, [])  # deferred rather than shown their question

    def test_a_generated_review_question_is_written_from_the_lesson(self) -> None:
        course = Course(id=uuid.uuid4(), title="C", slug=f"c-{uuid.uuid4().hex[:6]}")
        self.db.add(course)
        self.db.flush()
        lesson = Lesson(id=uuid.uuid4(), course_id=course.id, title="ER basics", order_index=0,
                        content_md="An entity set is a collection of similar entities.",
                        topic_tags=["dbms.er_model"])
        self.db.add(lesson)
        self.db.flush()
        scheduler.enrol_topic(self.db, self.user_id, "dbms.er_model", source_lesson_id=lesson.id)
        self.db.commit()

        prompts = []

        class _Capture:
            async def complete(self, messages, **kwargs):
                prompts.append(messages[0]["content"])
                return ""

        with patch("app.services.llm_client.get_llm", return_value=_Capture()):
            _run(scheduler.due_items(self.db, self.user_id))
        self.assertIn("An entity set is a collection of similar entities.", prompts[0])

    def test_topics_with_history_join_the_queue(self) -> None:
        """So the queue is not empty for the people who have done the most work."""
        self._bank()
        self.db.add(TopicMastery(user_id=self.user_id, topic_tag="dbms.sql_joins",
                                 mastery_score=0.4, attempts=2, correct=1))
        self.db.commit()
        items = _run(scheduler.due_items(self.db, self.user_id))
        self.assertEqual([i["topic_tag"] for i in items], ["dbms.sql_joins"])
        self.assertIn("prompt", items[0])

    def test_a_topic_with_no_question_is_deferred_not_dropped(self) -> None:
        scheduler.enrol_topic(self.db, self.user_id, "dbms.er_model")
        self.db.commit()
        with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
            items = _run(scheduler.due_items(self.db, self.user_id))
        self.assertEqual(items, [])
        self.assertEqual(self.db.query(ReviewItem).count(), 1)  # still queued

    def test_a_right_answer_pushes_the_topic_out(self) -> None:
        item = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
        self.db.commit()
        scheduler.record_answer(self.db, self.user_id, item.id, True)
        self.assertGreater(item.due_at.replace(tzinfo=timezone.utc), datetime.now(timezone.utc))
        self.assertEqual(item.streak, 1)

    def test_a_wrong_answer_brings_it_back_in_two_days(self) -> None:
        item = scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
        item.interval_days, item.streak = 20, 4
        self.db.commit()
        scheduler.record_answer(self.db, self.user_id, item.id, False)
        self.assertEqual(item.interval_days, 2)
        self.assertEqual(item.streak, 0)

    def test_answering_through_the_api_grades_and_reschedules(self) -> None:
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        self._bank()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id), "email": "t@local", "role": "student"
        }
        try:
            client = TestClient(app)
            scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
            self.db.commit()
            item = client.get("/api/review/today").json()["items"][0]

            # A wrong answer triggers misconception capture; stub the model so
            # the test neither spends quota nor depends on the network.
            belief = _FakeLLM(json.dumps({
                "misconception": "You believe a LEFT JOIN drops unmatched rows.",
                "confidence": 0.9,
            }))
            with patch("app.services.llm_client.get_llm", return_value=belief):
                wrong = client.post(
                    f"/api/review/{item['id']}/answer", json={"answer": "LEFT JOIN"}
                ).json()
            self.assertFalse(wrong["is_correct"])
            self.assertEqual(wrong["misconception"], "You believe a LEFT JOIN drops unmatched rows.")
            self.assertEqual(wrong["interval_days"], scheduler.WRONG_INTERVAL_DAYS)
        finally:
            app.dependency_overrides.clear()

    def test_an_abstained_grade_does_not_punish_the_schedule(self) -> None:
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        self._bank(qtype="short_answer")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id), "email": "t@local", "role": "student"
        }
        try:
            client = TestClient(app)
            scheduler.enrol_topic(self.db, self.user_id, "dbms.sql_joins")
            self.db.commit()
            item = client.get("/api/review/today").json()["items"][0]
            before = self.db.query(ReviewItem).first().interval_days

            with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
                r = client.post(
                    f"/api/review/{item['id']}/answer",
                    json={"answer": "rows that are in both tables"},
                ).json()
            self.assertTrue(r["needs_review"])
            self.assertEqual(self.db.query(ReviewItem).first().interval_days, before)
        finally:
            app.dependency_overrides.clear()

    def test_importing_the_scheduler_registers_enrolment(self) -> None:
        """The handler must register on import, not on first use of the page.

        Asserted via a reload rather than by reading the registry as found:
        other tests call clear_handlers(), a global mutation, so the registry's
        contents at this point depend on test order. That made the previous
        version pass alone and fail in the full suite.
        """
        import importlib

        from app.services import events

        events.clear_handlers("quiz.submitted")
        importlib.reload(scheduler)
        self.assertIn(
            "_enrol_from_quiz",
            [getattr(h, "__name__", "") for h in events.HANDLERS.get("quiz.submitted", [])],
        )

    def test_a_quiz_enrols_every_topic_it_touched(self) -> None:
        """The behaviour itself, independent of what is registered."""
        scheduler._enrol_from_quiz(
            self.db,
            self.user_id,
            {"answers": [
                {"topic_tag": "dbms.sql_joins", "is_correct": False},
                {"topic_tag": "dbms.er_model", "is_correct": True},
            ]},
        )
        tags = {r.topic_tag for r in self.db.query(ReviewItem).all()}
        self.assertEqual(tags, {"dbms.sql_joins", "dbms.er_model"})


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #

class TestRecommendations(_DBCase):
    def _course(self, *, private=False, owner=None, tags=("dbms.sql_joins",), n=2):
        course = Course(
            id=uuid.uuid4(), slug=f"c-{uuid.uuid4().hex[:6]}", title="Joins course",
            is_published=True, is_private=private, created_by=owner,
        )
        self.db.add(course)
        self.db.flush()
        lessons = []
        for i in range(n):
            lesson = Lesson(id=uuid.uuid4(), course_id=course.id, title=f"Lesson {i}",
                            order_index=i, topic_tags=list(tags))
            self.db.add(lesson)
            lessons.append(lesson)
        self.db.commit()
        return course, lessons

    def test_every_recommendation_carries_a_reason(self) -> None:
        self._course()
        items = recommender.recommend(self.db, self.user_id)
        self.assertTrue(items)
        for item in items:
            self.assertTrue(item["reason"].strip())

    def test_the_reason_quotes_the_real_number(self) -> None:
        self._course()
        self.db.add(TopicMastery(user_id=self.user_id, topic_tag="dbms.sql_joins",
                                 mastery_score=0.2, attempts=5, correct=1,
                                 last_practiced_at=datetime.now(timezone.utc)))
        self.db.commit()
        reasons = [i["reason"] for i in recommender.recommend(self.db, self.user_id)]
        self.assertTrue(any("20%" in r for r in reasons), reasons)

    def test_a_live_misconception_outranks_everything(self) -> None:
        self._course(tags=("dbms.er_model",), n=1)
        self._course(tags=("dbms.sql_joins",), n=1)
        self.db.add(TopicMastery(user_id=self.user_id, topic_tag="dbms.er_model",
                                 mastery_score=0.9, misconception="You believe keys must share names.",
                                 misconception_updated_at=datetime.now(timezone.utc),
                                 attempts=3, correct=2))
        self.db.commit()
        top = recommender.recommend(self.db, self.user_id)[0]
        self.assertEqual(top["topic_tag"], "dbms.er_model")
        self.assertIn("isn't quite right", top["reason"])

    def test_someone_elses_private_course_is_never_suggested(self) -> None:
        self._course(private=True, owner=uuid.uuid4())
        self.assertEqual(recommender.recommend(self.db, self.user_id), [])

    def test_your_own_private_course_is(self) -> None:
        self._course(private=True, owner=self.user_id)
        self.assertTrue(recommender.recommend(self.db, self.user_id))

    def test_finished_lessons_are_not_suggested(self) -> None:
        _course, lessons = self._course(n=1)
        self.db.add(LessonProgress(user_id=self.user_id, lesson_id=lessons[0].id, status="completed"))
        self.db.commit()
        self.assertEqual(recommender.recommend(self.db, self.user_id), [])

    def test_a_dismissed_recommendation_stays_gone(self) -> None:
        self._course(n=1)
        first = recommender.recommend(self.db, self.user_id)[0]
        self.assertTrue(recommender.dismiss(self.db, self.user_id, first["id"]))
        self.db.query(Recommendation).filter(Recommendation.is_dismissed.is_(False)).delete()
        self.db.commit()
        self.assertEqual(recommender.recommend(self.db, self.user_id), [])

    def test_the_daily_plan_fits_the_budget(self) -> None:
        self._course(n=6)
        plan = recommender.daily_plan(self.db, self.user_id, minutes=30)
        self.assertLessEqual(plan["planned_minutes"], 30)
        for item in plan["items"]:
            self.assertTrue(item["reason"])


if __name__ == "__main__":
    unittest.main()
