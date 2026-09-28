"""Uploaded notes -> a course that teaches them, and the vocabulary growing safely.

The regression these exist for, measured 2026-09-29: operating-systems slides
uploaded as a course came back as verbatim slide text, lessons titled after page
headers, every one tagged `dbms.er_model` - so "Practice this lesson" produced a
DBMS quiz aimed at a DBMS misconception the student already had.
"""

from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import ReviewItem, Topic
from app.models.course import Course, Enrollment, Lesson
from app.models.user import User
from app.services import notes_course as nc
from app.services import topics


def _run(coro):
    return asyncio.run(coro)


class _ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def complete(self, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        return self.replies.pop(0) if self.replies else ""


class _DeadLLM:
    async def complete(self, messages, **kwargs):
        raise RuntimeError("429 quota exceeded")


VOCAB = [
    ("dbms.er_model", "ER model and keys", "dbms"),
    ("dbms.sql_joins", "SQL joins", "dbms"),
    ("python.loops", "Loops and iteration", "python"),
]

OS_NOTES = "\n".join(
    [
        "Dept. of CSE, BUET",
        "CSE 313 Operating Systems",
        *["Interprocess communication lets processes exchange data safely."] * 20,
        *["A race condition happens when the outcome depends on timing."] * 20,
        *["A semaphore is an integer with atomic wait and signal operations."] * 20,
    ]
)

LESSON_BODY = "A semaphore is a counter that processes wait on and signal. " * 10


def _os_outline(**overrides):
    payload = {
        "title": "Process Synchronisation",
        "description": "How processes coordinate safely.",
        "subject": "os",
        "difficulty": "intermediate",
        "lessons": [
            {
                "title": "Interprocess Communication",
                "summary": "Why processes need to talk and how.",
                "chunks": [1],
                "topic_tag": "os.ipc",
                "topic_label": "Interprocess communication",
            },
            {
                "title": "Race Conditions",
                "summary": "What goes wrong without coordination.",
                "chunks": [2],
                "topic_tag": "os.race_conditions",
                "topic_label": "Race conditions",
            },
            {
                "title": "Semaphores",
                "summary": "The classic fix.",
                "chunks": [3],
                "topic_tag": "os.semaphores",
                "topic_label": "Semaphores",
            },
        ],
    }
    payload.update(overrides)
    return payload


class Base_(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False)

    def setUp(self) -> None:
        self.db = self.Session()
        self.user_id = uuid.uuid4()
        self.db.add(User(id=self.user_id, email=f"{self.user_id.hex[:8]}@t.local", full_name="T"))
        for tag, label, subject in VOCAB:
            self.db.add(Topic(tag=tag, label=label, subject=subject, is_active=True))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        for model in (ReviewItem, Enrollment, Lesson, Course, Topic, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()


class TestVocabularyGrowth(Base_):
    def test_an_existing_tag_is_kept(self) -> None:
        self.assertEqual(
            topics.register(self.db, [{"tag": "dbms.sql_joins", "label": "Joins"}]),
            {"dbms.sql_joins": "dbms.sql_joins"},
        )

    def test_a_labelled_proposal_becomes_a_topic(self) -> None:
        mapping = topics.register(
            self.db, [{"tag": "os.semaphores", "label": "Semaphores", "subject": "os"}]
        )
        self.assertEqual(mapping, {"os.semaphores": "os.semaphores"})
        self.assertTrue(topics.is_known(self.db, "os.semaphores"))

    def test_a_proposal_without_a_label_is_refused(self) -> None:
        """Otherwise every stray tag a model emits becomes permanent."""
        self.assertEqual(topics.register(self.db, [{"tag": "os.semaphores"}]), {})
        self.assertFalse(topics.is_known(self.db, "os.semaphores"))

    def test_a_malformed_tag_is_refused(self) -> None:
        for bad in ("semaphores", "os.", "a.b.c", "OS Semaphores!!"):
            self.assertEqual(topics.register(self.db, [{"tag": bad, "label": "x"}]), {}, bad)

    def test_a_plural_variant_reuses_the_existing_tag(self) -> None:
        """`os.semaphore` beside `os.semaphores` is the fragmentation to avoid."""
        topics.register(self.db, [{"tag": "os.semaphores", "label": "Semaphores"}])
        self.assertEqual(
            topics.register(self.db, [{"tag": "os.semaphore", "label": "Semaphore basics"}]),
            {"os.semaphore": "os.semaphores"},
        )

    def test_process_and_processes_match_but_do_not_mangle(self) -> None:
        topics.register(self.db, [{"tag": "os.process", "label": "Processes"}])
        self.assertEqual(
            topics.register(self.db, [{"tag": "os.processes", "label": "Process model"}]),
            {"os.processes": "os.process"},
        )

    def test_the_same_label_reuses_the_existing_tag(self) -> None:
        self.assertEqual(
            topics.register(self.db, [{"tag": "sql.joins", "label": "SQL joins"}]),
            {"sql.joins": "dbms.sql_joins"},
        )

    def test_new_topics_per_call_are_capped(self) -> None:
        proposals = [{"tag": f"bio.topic_{i}", "label": f"Topic {i}"} for i in range(20)]
        self.assertEqual(len(topics.register(self.db, proposals, limit=3)), 3)


class TestChunking(unittest.TestCase):
    def test_chunks_are_bounded_and_lose_nothing_short(self) -> None:
        chunks = nc.chunk_notes(OS_NOTES, size=500)
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c) <= 600 for c in chunks))
        self.assertIn("semaphore", chunks[-1].lower())

    def test_a_single_huge_line_is_cut(self) -> None:
        chunks = nc.chunk_notes("x" * 5000, size=1000)
        self.assertEqual(len(chunks), 5)

    def test_text_past_the_limit_is_dropped(self) -> None:
        chunks = nc.chunk_notes("word " * 50_000, size=1000, limit=10_000)
        self.assertLessEqual(sum(len(c) for c in chunks), 10_000)


class TestOutlineValidation(Base_):
    def test_os_notes_are_never_filed_under_dbms(self) -> None:
        """The bug: every OS lesson came back tagged dbms.er_model."""
        out = nc.validate_outline(self.db, _os_outline(), ["a", "b", "c"])
        tags = [l["topic_tag"] for l in out["lessons"]]
        self.assertEqual(tags, ["os.ipc", "os.race_conditions", "os.semaphores"])
        self.assertFalse(any(t.startswith("dbms.") for t in tags))

    def test_an_unlabelled_unknown_tag_drops_the_lesson(self) -> None:
        payload = _os_outline()
        payload["lessons"][2].pop("topic_label")
        payload["lessons"][2]["topic_tag"] = "os.never_seen"
        out = nc.validate_outline(self.db, payload, ["a", "b", "c"])
        self.assertEqual(len(out["lessons"]), 2)

    def test_out_of_range_chunks_fall_back_to_word_overlap(self) -> None:
        payload = _os_outline()
        payload["lessons"][2]["chunks"] = [99, "x"]
        chunks = ["ipc text", "race timing text", "semaphore wait signal semaphores"]
        out = nc.validate_outline(self.db, payload, chunks)
        self.assertIn(3, out["lessons"][2]["chunks"])

    def test_notes_with_no_study_material_give_no_outline(self) -> None:
        self.assertIsNone(nc.validate_outline(self.db, {"lessons": []}, ["a"]))


class TestBuildCourse(Base_):
    def _llm(self, bodies=None):
        bodies = bodies if bodies is not None else [LESSON_BODY] * 3
        return _ScriptedLLM([json.dumps(_os_outline())] + bodies)

    def _build(self, llm, **kw):
        with patch("app.services.llm_client.get_llm", return_value=llm):
            return _run(
                nc.build_course_from_notes(
                    self.db, user_id=self.user_id, text=OS_NOTES, filename="OS.pdf", **kw
                )
            )

    def test_builds_a_taught_course_with_the_right_topics(self) -> None:
        result = self._build(self._llm())

        course = self.db.query(Course).filter(Course.id == uuid.UUID(result["course_id"])).one()
        self.assertEqual(course.source, "uploaded")
        self.assertTrue(course.is_private)
        self.assertEqual(course.title, "Process Synchronisation")

        lessons = self.db.query(Lesson).filter(Lesson.course_id == course.id).order_by(Lesson.order_index).all()
        self.assertEqual([l.title for l in lessons], ["Interprocess Communication", "Race Conditions", "Semaphores"])
        self.assertEqual(lessons[2].topic_tags, ["os.semaphores"])
        # Taught, not transcribed: the body is the model's lesson.
        self.assertEqual(lessons[2].content_md, LESSON_BODY.strip())

        self.assertEqual(result["topics"], ["os.ipc", "os.race_conditions", "os.semaphores"])
        self.assertEqual(len(result["lessons"]), 3)
        self.assertNotIn("content_md", result["lessons"][0])

    def test_each_lesson_is_taught_from_its_own_notes(self) -> None:
        llm = self._llm()
        chunks = nc.chunk_notes(OS_NOTES)
        self._build(llm)
        # prompts[0] is the outline; prompts[3] writes the Semaphores lesson from chunk 3.
        self.assertIn(chunks[2], llm.prompts[3])
        if len(chunks) > 1:
            self.assertNotIn(chunks[0], llm.prompts[3])

    def test_the_outline_sees_the_vocabulary_and_the_rule(self) -> None:
        llm = self._llm()
        self._build(llm)
        self.assertIn("dbms.er_model - ER model and keys", llm.prompts[0])
        self.assertIn("NEVER use a tag from an unrelated subject", llm.prompts[0])
        self.assertIn("[[1]]", llm.prompts[0])

    def test_a_custom_title_wins(self) -> None:
        result = self._build(self._llm(), custom_title="My OS notes")
        self.assertEqual(result["title"], "My OS notes")

    def test_enrols_and_seeds_review_for_each_new_topic(self) -> None:
        self._build(self._llm())
        self.assertEqual(self.db.query(Enrollment).filter(Enrollment.user_id == self.user_id).count(), 1)
        seeded = {r.topic_tag for r in self.db.query(ReviewItem).filter(ReviewItem.user_id == self.user_id)}
        self.assertEqual(seeded, {"os.ipc", "os.race_conditions", "os.semaphores"})

    def test_a_failed_lesson_shows_its_notes_honestly(self) -> None:
        """One bad call costs a thin lesson, not the whole course."""
        self._build(self._llm([LESSON_BODY, "", LESSON_BODY]))
        second = self.db.query(Lesson).filter(Lesson.order_index == 1).one()
        self.assertIn("From your notes", second.content_md)
        self.assertEqual(second.topic_tags, ["os.race_conditions"])

    def test_a_dead_provider_saves_nothing_and_says_why(self) -> None:
        with patch("app.services.llm_client.get_llm", return_value=_DeadLLM()):
            with self.assertRaises(RuntimeError) as ctx:
                _run(nc.build_course_from_notes(self.db, user_id=self.user_id, text=OS_NOTES, filename="OS.pdf"))
        # jobs._student_facing_error turns this into "over its request limit".
        self.assertIn("429", str(ctx.exception))
        self.assertEqual(self.db.query(Course).count(), 0)

    def test_notes_without_study_material_are_refused(self) -> None:
        llm = _ScriptedLLM([json.dumps({"lessons": []})])
        with patch("app.services.llm_client.get_llm", return_value=llm):
            with self.assertRaises(RuntimeError):
                _run(nc.build_course_from_notes(self.db, user_id=self.user_id, text=OS_NOTES, filename="rules.pdf"))
        self.assertEqual(self.db.query(Course).count(), 0)


class TestQuizStaysOnTheLesson(unittest.TestCase):
    def test_quiz_prompt_requires_questions_answerable_from_the_lesson(self) -> None:
        from app.services.prompts import QUIZ_GENERATION_PROMPT

        self.assertIn("answerable from the lesson below alone", QUIZ_GENERATION_PROMPT)

    def test_misconception_hint_is_ignored_when_the_lesson_is_elsewhere(self) -> None:
        from app.services.quiz_generator import MISCONCEPTION_HINT

        self.assertIn("ignore this note completely", MISCONCEPTION_HINT)


if __name__ == "__main__":
    unittest.main()
