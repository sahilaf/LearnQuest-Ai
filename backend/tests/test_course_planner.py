"""AI course generation: outline validation, lesson writing and persistence.

The outline tests matter most. A course is only useful to this product if its
lessons carry tags the rest of the system recognises - an untagged lesson cannot
feed mastery, so it cannot feed the misconception engine, which is the entire
reason a learner is reading it.
"""

from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import Topic
from app.models.course import Course, Enrollment, Lesson
from app.models.user import User
from app.services import course_planner as cp


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class _ScriptedLLM:
    """Returns each queued reply in turn: outline first, then one per lesson."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def complete(self, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        return self.replies.pop(0) if self.replies else ""


class _DeadLLM:
    async def complete(self, messages, **kwargs):
        raise RuntimeError("provider down")


TAGS = [
    ("dbms.sql_joins", "SQL joins", "dbms"),
    ("dbms.er_model", "ER model and keys", "dbms"),
    ("dbms.normalization", "Normalization", "dbms"),
    ("python.loops", "Loops and iteration", "python"),
]

LESSON_BODY = (
    "A join combines rows from two tables. " * 12
)  # comfortably over MIN_LESSON_CHARS


def _outline(tags, title="Relational databases, quickly"):
    return json.dumps(
        {
            "title": title,
            "description": "A short path through the relational model.",
            "subject": "dbms",
            "difficulty": "beginner",
            "estimated_hours": 2,
            "lessons": [
                {
                    "title": f"Lesson about {tag}",
                    "topic_tag": tag,
                    "summary": f"Covers {tag} and why it matters.",
                }
                for tag in tags
            ],
        }
    )


class PlannerBase(unittest.TestCase):
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
        self.db.add(
            User(id=self.user_id, email=f"{self.user_id.hex[:8]}@t.local", full_name="T")
        )
        for tag, label, subject in TAGS:
            self.db.add(Topic(tag=tag, label=label, subject=subject, is_active=True))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        for model in (Enrollment, Lesson, Course, Topic, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()


class TestOutlineValidation(PlannerBase):
    def _validate(self, payload, n=4):
        return cp.validate_outline(self.db, payload, n)

    def test_a_good_outline_survives(self) -> None:
        out = self._validate(json.loads(_outline([t[0] for t in TAGS[:3]])))
        self.assertIsNotNone(out)
        self.assertEqual(len(out["lessons"]), 3)
        self.assertEqual(out["difficulty"], "beginner")

    def test_lessons_with_invented_tags_are_dropped(self) -> None:
        """An untagged lesson cannot feed mastery, so it cannot feed anything."""
        payload = json.loads(_outline(["dbms.sql_joins", "dbms.er_model", "dbms.normalization"]))
        payload["lessons"].append(
            {"title": "Something about SQL", "topic_tag": "sql.joins", "summary": "x"}
        )
        out = self._validate(payload, n=6)
        self.assertEqual(len(out["lessons"]), 3)
        self.assertNotIn("sql.joins", [l["topic_tag"] for l in out["lessons"]])

    def test_a_labelled_new_topic_is_registered_not_forced_onto_dbms(self) -> None:
        """A goal outside the vocabulary used to be tagged with "the closest" -
        an operating-systems course came back filed under DBMS."""
        payload = json.loads(_outline(["dbms.sql_joins", "dbms.er_model"]))
        payload["lessons"].append(
            {
                "title": "Semaphores",
                "topic_tag": "os.semaphores",
                "topic_label": "Semaphores",
                "summary": "x",
            }
        )
        out = self._validate(payload, n=6)
        self.assertEqual(out["lessons"][-1]["topic_tag"], "os.semaphores")
        self.assertIsNotNone(self.db.query(Topic).filter(Topic.tag == "os.semaphores").first())

    def test_the_planner_is_told_not_to_borrow_unrelated_tags(self) -> None:
        from app.services.prompts import COURSE_OUTLINE_PROMPT, TOPIC_RULES

        self.assertIn("{topic_rules}", COURSE_OUTLINE_PROMPT)
        self.assertIn("NEVER use a tag from an unrelated subject", TOPIC_RULES)
        self.assertNotIn("return the closest ones", COURSE_OUTLINE_PROMPT)

    def test_too_few_usable_lessons_is_rejected_outright(self) -> None:
        """Better no course than a two-lesson stub the learner paid a minute for."""
        payload = json.loads(_outline(["dbms.sql_joins"]))
        payload["lessons"].append(
            {"title": "Invented", "topic_tag": "astrology.houses", "summary": "x"}
        )
        self.assertIsNone(self._validate(payload))

    def test_duplicate_lesson_titles_collapse(self) -> None:
        payload = json.loads(_outline([t[0] for t in TAGS[:3]]))
        payload["lessons"].append(dict(payload["lessons"][0]))
        out = self._validate(payload, n=6)
        self.assertEqual(len(out["lessons"]), 3)

    def test_lesson_count_is_capped(self) -> None:
        payload = json.loads(_outline([t[0] for t in TAGS]))
        out = self._validate(payload, n=3)
        self.assertEqual(len(out["lessons"]), 3)

    def test_a_nonsense_difficulty_falls_back(self) -> None:
        payload = json.loads(_outline([t[0] for t in TAGS[:3]]))
        payload["difficulty"] = "galaxy-brain"
        self.assertEqual(self._validate(payload)["difficulty"], "beginner")

    def test_junk_returns_none(self) -> None:
        self.assertIsNone(self._validate("not a dict"))
        self.assertIsNone(self._validate({"title": "x"}))
        self.assertIsNone(self._validate({"title": "Fine title", "lessons": "nope"}))


class TestSlug(PlannerBase):
    def test_slugs_do_not_collide_for_the_same_title(self) -> None:
        """Two learners both asking to "Learn SQL" must not clash on a unique column."""
        a = cp.slugify("Learn SQL")
        b = cp.slugify("Learn SQL")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("learn-sql-"))

    def test_slug_survives_an_unhelpful_title(self) -> None:
        self.assertTrue(cp.slugify("!!! ???").startswith("course-"))


class TestGeneration(PlannerBase):
    def _llm(self, n_lessons=3, body=LESSON_BODY):
        return _ScriptedLLM(
            [_outline([t[0] for t in TAGS[:n_lessons]])] + [body] * n_lessons
        )

    def test_generates_persists_and_enrols(self) -> None:
        llm = self._llm()
        with patch("app.services.llm_client.get_llm", return_value=llm):
            result = _run(
                cp.generate_course(
                    self.db, user_id=self.user_id, goal="I want to learn databases", n_lessons=3
                )
            )

        self.assertEqual(result["lessons"], 3)
        course = self.db.query(Course).filter(Course.id == uuid.UUID(result["course_id"])).first()
        self.assertEqual(course.source, "ai_generated")
        self.assertTrue(course.is_private)
        self.assertTrue(course.is_published)
        self.assertEqual(course.created_by, self.user_id)

        lessons = (
            self.db.query(Lesson)
            .filter(Lesson.course_id == course.id)
            .order_by(Lesson.order_index)
            .all()
        )
        self.assertEqual(len(lessons), 3)
        self.assertEqual([l.order_index for l in lessons], [0, 1, 2])
        for lesson in lessons:
            self.assertEqual(len(lesson.topic_tags), 1)
            self.assertIn(lesson.topic_tags[0], [t[0] for t in TAGS])

        # Without the enrolment the course appears nowhere the learner looks.
        self.assertEqual(
            self.db.query(Enrollment)
            .filter(Enrollment.user_id == self.user_id, Enrollment.course_id == course.id)
            .count(),
            1,
        )

    def test_each_lesson_is_told_what_came_before(self) -> None:
        """Otherwise lesson 3 re-teaches lesson 1."""
        llm = self._llm()
        with patch("app.services.llm_client.get_llm", return_value=llm):
            _run(
                cp.generate_course(
                    self.db, user_id=self.user_id, goal="databases", n_lessons=3
                )
            )
        # prompts[0] is the outline; the last lesson prompt lists the earlier ones.
        self.assertIn("Earlier lessons", llm.prompts[-1])
        self.assertIn("Lesson about dbms.sql_joins", llm.prompts[-1])

    def test_a_thin_lesson_falls_back_to_its_summary(self) -> None:
        """One bad call should cost a thin lesson, not the whole course."""
        llm = _ScriptedLLM(
            [_outline([t[0] for t in TAGS[:3]]), LESSON_BODY, "too short", LESSON_BODY]
        )
        with patch("app.services.llm_client.get_llm", return_value=llm):
            result = _run(
                cp.generate_course(
                    self.db, user_id=self.user_id, goal="databases", n_lessons=3
                )
            )

        self.assertEqual(result["lessons"], 3)
        second = (
            self.db.query(Lesson)
            .filter(Lesson.course_id == uuid.UUID(result["course_id"]), Lesson.order_index == 1)
            .first()
        )
        self.assertIn("Covers", second.content_md)

    def test_a_dead_provider_saves_nothing(self) -> None:
        with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
            with self.assertRaises(RuntimeError):
                _run(cp.generate_course(self.db, user_id=self.user_id, goal="databases"))
        self.assertEqual(self.db.query(Course).count(), 0)
        self.assertEqual(self.db.query(Enrollment).count(), 0)

    def test_an_empty_goal_is_refused_before_any_call(self) -> None:
        with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
            with self.assertRaises(ValueError):
                _run(cp.generate_course(self.db, user_id=self.user_id, goal="  "))

    def test_the_vocabulary_is_given_to_the_planner(self) -> None:
        llm = self._llm()
        with patch("app.services.llm_client.get_llm", return_value=llm):
            _run(
                cp.generate_course(
                    self.db, user_id=self.user_id, goal="databases", n_lessons=3
                )
            )
        self.assertIn("dbms.sql_joins - SQL joins", llm.prompts[0])


if __name__ == "__main__":
    unittest.main()
