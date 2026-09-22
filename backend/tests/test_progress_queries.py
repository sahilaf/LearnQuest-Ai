"""Query-count and correctness guards for the dashboard's progress endpoints.

These endpoints used to run one LessonProgress query per enrolled course. Every
query is a network round trip to Supabase (measured 2026-09-22: ~75 ms), so ten
enrolled courses cost roughly 825 ms on a single endpoint.

The count is asserted, not just the output: a future `joinedload` removed or a
lookup moved back inside the loop would still return the right answer while
quietly making the dashboard slow again.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.course import Course, Enrollment, Lesson
from app.models.progress import LessonProgress
from app.models.user import User


class ProgressQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.selects = {"n": 0}

        @event.listens_for(cls.engine, "before_cursor_execute")
        def _count(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                cls.selects["n"] += 1

    def tearDown(self) -> None:
        db = self.Session()
        for model in (LessonProgress, Enrollment, Lesson, Course, User):
            db.query(model).delete()
        db.commit()
        db.close()

    def _seed(self, courses: int, lessons_each: int = 4, completed_each: int = 2):
        db = self.Session()
        user_id = uuid.uuid4()
        db.add(User(id=user_id, email=f"{user_id.hex[:8]}@t.local", full_name="T"))

        for c in range(courses):
            course = Course(
                id=uuid.uuid4(),
                slug=f"c{c}-{uuid.uuid4().hex[:6]}",
                title=f"Course {c}",
                is_published=True,
            )
            db.add(course)
            for i in range(lessons_each):
                lesson = Lesson(
                    id=uuid.uuid4(), course_id=course.id, title=f"L{i}", order_index=i
                )
                db.add(lesson)
                if i < completed_each:
                    db.add(
                        LessonProgress(
                            id=uuid.uuid4(),
                            user_id=user_id,
                            lesson_id=lesson.id,
                            status="completed",
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
            db.add(
                Enrollment(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    course_id=course.id,
                    enrolled_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
        db.close()
        return user_id

    def _measure(self, call, user_id):
        """Run `call` on a fresh session and report (result, select_count).

        The session must be new: reusing the one that created the rows hides
        every lazy load behind SQLAlchemy's identity map, which would make this
        test pass even with the N+1 restored.
        """
        db = self.Session()
        type(self).selects["n"] = 0
        try:
            result = call(db, user_id)
        finally:
            count = type(self).selects["n"]
            db.close()
        return result, count

    # --- query counts ---------------------------------------------------

    def test_progress_query_count_does_not_grow_with_courses(self) -> None:
        from app.routers.progress import my_progress

        counts = []
        for courses in (1, 10):
            user_id = self._seed(courses)
            _, count = self._measure(
                lambda db, uid: my_progress(user={"id": str(uid)}, db=db), user_id
            )
            counts.append(count)
            self.tearDown()

        self.assertEqual(counts[0], counts[1], "query count grows with enrolled courses")
        self.assertLessEqual(counts[1], 3)

    def test_enrollments_query_count_does_not_grow_with_courses(self) -> None:
        from app.routers.progress import my_enrollments

        counts = []
        for courses in (1, 10):
            user_id = self._seed(courses)
            _, count = self._measure(
                lambda db, uid: my_enrollments(user={"id": str(uid)}, db=db), user_id
            )
            counts.append(count)
            self.tearDown()

        self.assertEqual(counts[0], counts[1], "query count grows with enrolled courses")
        self.assertLessEqual(counts[1], 3)

    # --- the answer is still right --------------------------------------

    def test_progress_still_reports_the_right_completion(self) -> None:
        from app.routers.progress import my_progress

        user_id = self._seed(courses=3, lessons_each=4, completed_each=2)
        result, _ = self._measure(
            lambda db, uid: my_progress(user={"id": str(uid)}, db=db), user_id
        )

        self.assertEqual(len(result["items"]), 3)
        for item in result["items"]:
            self.assertEqual(item["total_lessons"], 4)
            self.assertEqual(item["completed_lessons"], 2)
            self.assertEqual(item["completion_percentage"], 50.0)
            self.assertEqual(len(item["completed_lesson_ids"]), 2)

    def test_enrollments_next_lesson_is_the_first_unfinished_one(self) -> None:
        from app.routers.progress import my_enrollments

        user_id = self._seed(courses=1, lessons_each=4, completed_each=2)
        result, _ = self._measure(
            lambda db, uid: my_enrollments(user={"id": str(uid)}, db=db), user_id
        )

        item = result["items"][0]
        self.assertEqual(item["completed_lessons"], 2)
        self.assertEqual(item["completion_percentage"], 50.0)
        # Lessons 0 and 1 are done, so the next one is "L2".
        self.assertEqual(item["next_lesson_title"], "L2")

    def test_no_progress_rows_reads_as_zero_not_as_an_error(self) -> None:
        from app.routers.progress import my_progress

        user_id = self._seed(courses=2, lessons_each=3, completed_each=0)
        result, _ = self._measure(
            lambda db, uid: my_progress(user={"id": str(uid)}, db=db), user_id
        )

        self.assertEqual(len(result["items"]), 2)
        for item in result["items"]:
            self.assertEqual(item["completed_lessons"], 0)
            self.assertEqual(item["completion_percentage"], 0.0)


if __name__ == "__main__":
    unittest.main()
