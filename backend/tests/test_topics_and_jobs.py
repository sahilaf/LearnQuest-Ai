"""Foundations for generated content: the tag vocabulary and the job runner.

The vocabulary tests matter more than they look. `topic_tag` is the join key
between mastery, misconceptions and the roadmap, so a generated tag
that slips through unvalidated does not cause an error - it causes a mastery row
that nothing will ever look up again, and a misconception map that quietly
fragments into singletons.
"""

from __future__ import annotations

import asyncio
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import GenerationJob, Topic
from app.models.user import User
from app.services import jobs as jobs_service
from app.services import topics as topics_service

SEED = [
    ("dbms.sql_joins", "SQL joins", "dbms"),
    ("dbms.er_model", "ER model and keys", "dbms"),
    ("python.loops", "Loops and iteration", "python"),
]


class Base_(unittest.TestCase):
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
        for tag, label, subject in SEED:
            self.db.add(Topic(tag=tag, label=label, subject=subject, is_active=True))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.rollback()
        for model in (GenerationJob, Topic, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()


class TestVocabulary(Base_):
    def test_known_tags_survive(self) -> None:
        self.assertEqual(
            topics_service.resolve(self.db, ["dbms.sql_joins", "python.loops"]),
            ["dbms.sql_joins", "python.loops"],
        )

    def test_invented_tags_are_dropped(self) -> None:
        """The whole point: a model's improvised tag must not reach the data.

        Left in, each of these becomes its own topic_mastery row and the
        student's misconception is recorded against a tag nothing else uses.
        """
        resolved = topics_service.resolve(
            self.db,
            ["sql.joins", "databases.inner_join", "dbms.joins", "dbms.sql_joins"],
        )
        self.assertEqual(resolved, ["dbms.sql_joins"])

    def test_casing_and_separators_are_normalised_not_invented(self) -> None:
        self.assertEqual(
            topics_service.resolve(self.db, ["  DBMS.SQL-JOINS "]), ["dbms.sql_joins"]
        )
        # Normalising must not manufacture a match that is not there.
        self.assertEqual(topics_service.resolve(self.db, ["DBMS.JOINS"]), [])

    def test_duplicates_collapse(self) -> None:
        self.assertEqual(
            topics_service.resolve(self.db, ["dbms.sql_joins", "dbms.sql_joins"]),
            ["dbms.sql_joins"],
        )

    def test_nothing_recognised_returns_empty_rather_than_guessing(self) -> None:
        self.assertEqual(topics_service.resolve(self.db, ["astrology.houses"]), [])

    def test_retired_tags_are_not_offered(self) -> None:
        self.db.query(Topic).filter(Topic.tag == "python.loops").update(
            {"is_active": False}
        )
        self.db.commit()
        self.assertNotIn("python.loops", topics_service.active_tags(self.db))
        self.assertEqual(topics_service.resolve(self.db, ["python.loops"]), [])

    def test_prompt_block_lists_tag_and_label(self) -> None:
        block = topics_service.prompt_block(self.db)
        self.assertIn("dbms.sql_joins - SQL joins", block)
        self.assertEqual(len(block.strip().splitlines()), len(SEED))

    def test_prompt_block_can_narrow_to_one_subject(self) -> None:
        block = topics_service.prompt_block(self.db, subject="dbms")
        self.assertIn("dbms.sql_joins", block)
        self.assertNotIn("python.loops", block)


class TestJobs(Base_):
    def test_a_job_starts_queued(self) -> None:
        job = jobs_service.create_job(self.db, self.user_id, "quiz", {"n": 5})
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.params["n"], 5)

    def test_unknown_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            jobs_service.create_job(self.db, self.user_id, "sandwich", {})

    def test_daily_cap_is_enforced(self) -> None:
        for _ in range(jobs_service.DAILY_JOBS_PER_USER):
            jobs_service.create_job(self.db, self.user_id, "quiz", {})
        with self.assertRaises(jobs_service.JobLimitReached):
            jobs_service.create_job(self.db, self.user_id, "quiz", {})

    def test_failed_jobs_do_not_consume_the_allowance(self) -> None:
        """A failure on our side should not cost the student a generation."""
        job = jobs_service.create_job(self.db, self.user_id, "quiz", {})
        job.status = "failed"
        self.db.commit()
        self.assertEqual(jobs_service.jobs_used_today(self.db, self.user_id), 0)

    def test_the_cap_is_per_user(self) -> None:
        other = uuid.uuid4()
        self.db.add(User(id=other, email="other@t.local", full_name="O"))
        self.db.commit()
        for _ in range(jobs_service.DAILY_JOBS_PER_USER):
            jobs_service.create_job(self.db, self.user_id, "quiz", {})
        # The other user still has their full allowance.
        jobs_service.create_job(self.db, other, "quiz", {})

    def test_a_job_belongs_to_its_owner(self) -> None:
        job = jobs_service.create_job(self.db, self.user_id, "quiz", {})
        self.assertIsNotNone(jobs_service.get_job(self.db, job.id, self.user_id))
        self.assertIsNone(jobs_service.get_job(self.db, job.id, uuid.uuid4()))

    def test_stale_running_jobs_are_reaped(self) -> None:
        """A restart mid-generation must not leave a job polled forever."""
        job = jobs_service.create_job(self.db, self.user_id, "course", {})
        job.status = "running"
        job.created_at = datetime.now(timezone.utc) - timedelta(
            minutes=jobs_service.STALE_AFTER_MINUTES + 5
        )
        self.db.commit()

        self.assertEqual(jobs_service.reap_stale_jobs(self.db), 1)
        self.db.refresh(job)
        self.assertEqual(job.status, "failed")
        self.assertIn("interrupted", job.error)

    def test_a_recent_running_job_is_left_alone(self) -> None:
        job = jobs_service.create_job(self.db, self.user_id, "course", {})
        job.status = "running"
        self.db.commit()
        self.assertEqual(jobs_service.reap_stale_jobs(self.db), 0)
        self.db.refresh(job)
        self.assertEqual(job.status, "running")

    def test_quota_errors_are_written_for_a_student(self) -> None:
        """Nobody can act on "429 Too Many Requests"."""
        message = jobs_service._student_facing_error(
            RuntimeError("Client error '429 Too Many Requests' for url ...")
        )
        self.assertIn("limit", message.lower())
        self.assertNotIn("429", message)


if __name__ == "__main__":
    unittest.main()
