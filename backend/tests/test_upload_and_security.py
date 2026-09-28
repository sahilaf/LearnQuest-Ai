"""Tests for Member 3's Week 3 tasks: Upload notes to course pipeline and security pass.

OWNER: Member 3. See plan.md §6.13, §8.6, and CHECKLIST.md Slot 11.
"""

from __future__ import annotations

import io
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import CurrentUser, get_current_user
from app.main import app
from app.models.ai import ReviewItem, Topic
from app.models.course import Course, Enrollment, Lesson
from app.models.user import User
from app.services.notes_extractor import extract_text_from_file, validate_file


class TestUploadAndSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.db.rollback()
        for model in (ReviewItem, Enrollment, Lesson, Course, Topic, User):
            self.db.query(model).delete()
        self.db.commit()

        # Seed test user (student 1)
        self.user1_id = uuid.uuid4()
        self.user1 = User(
            id=self.user1_id,
            email="student1@learnquest.local",
            full_name="Student One",
            role="student",
        )
        # Seed test user 2 (student 2 / stranger)
        self.user2_id = uuid.uuid4()
        self.user2 = User(
            id=self.user2_id,
            email="student2@learnquest.local",
            full_name="Student Two",
            role="student",
        )
        self.db.add_all([self.user1, self.user2])

        # Seed standard topic tags into vocabulary
        self.db.add_all([
            Topic(tag="sql.joins", label="SQL Joins (INNER, LEFT, RIGHT, FULL)", subject="Database Management"),
            Topic(tag="sql.basics", label="SQL Basics & Filtering", subject="Database Management"),
            Topic(tag="dbms.normalization", label="Database Normalization", subject="Database Management"),
            Topic(tag="python.loops", label="Python Loops & Iteration", subject="Programming"),
        ])
        self.db.commit()

        # Wire dependency override for get_db
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.rollback()
        for model in (ReviewItem, Enrollment, Lesson, Course, Topic, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()


    # =========================================================================
    # 1. Validation & Text Extraction Unit Tests
    # =========================================================================

    def test_validate_file_rejects_empty_filename(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_file("", b"some content here")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_file_rejects_unsupported_extensions(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_file("malicious.exe", b"binary content")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported file format", ctx.exception.detail)

    def test_validate_file_rejects_oversized_file(self):
        huge_content = b"a" * (10 * 1024 * 1024 + 1)
        with self.assertRaises(HTTPException) as ctx:
            validate_file("notes.txt", huge_content)
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertIn("exceeds maximum upload size", ctx.exception.detail)

    def test_extract_text_from_markdown(self):
        md = "# Introduction to SQL\n\nSQL stands for Structured Query Language."
        extracted = extract_text_from_file("notes.md", md.encode("utf-8"))
        self.assertEqual(extracted, md)

    def test_extract_text_from_pdf_stream(self):
        # Create a small valid PDF in memory using pypdf
        import pypdf

        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        # Note: blank page has no text, so test extraction error handling
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        # Blank PDF without text should raise 400 scanned/empty
        with self.assertRaises(HTTPException) as ctx:
            extract_text_from_file("document.pdf", pdf_bytes)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Could not extract readable text", ctx.exception.detail)

    # Splitting, tagging and persistence moved to services/notes_course.py on
    # 2026-09-29 and are covered by tests/test_notes_course.py. The keyword
    # tagger tested here filed unrelated notes under the first topic in the
    # vocabulary - one test asserted exactly that, for notes about cooking.

    # =========================================================================
    # 4. HTTP Endpoint & Security Tests
    # =========================================================================

    def test_api_course_upload_endpoint(self):
        # Override CurrentUser as user1
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user1_id),
            "email": self.user1.email,
            "role": "student",
        }

        doc = b"# Section 1: Intro to Python Loops\nFor loops and while loops iterate over sequences.\n\n# Section 2: Loop Control\nBreak and continue statements control loop execution flow."
        # Building the course is a background job; the route's job is to read
        # the file, refuse bad ones at once, and hand back something to poll.
        with patch("app.services.jobs.schedule") as scheduled:
            response = self.client.post(
                "/api/courses/upload",
                files={"file": ("python_notes.md", doc, "text/markdown")},
            )
        self.assertEqual(response.status_code, 202, response.text)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["status"], "queued")
        scheduled.assert_called_once()

    def test_api_course_upload_rejects_a_bad_file_before_queueing(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user1_id),
            "email": self.user1.email,
            "role": "student",
        }
        with patch("app.services.jobs.schedule") as scheduled:
            response = self.client.post(
                "/api/courses/upload",
                files={"file": ("virus.exe", b"MZ binary content", "application/octet-stream")},
            )
        self.assertEqual(response.status_code, 400, response.text)
        scheduled.assert_not_called()

    def test_security_private_course_hidden_from_public_catalog(self):
        # Create a private course for user1
        c = Course(
            id=uuid.uuid4(),
            title="User 1 Secret Notes",
            slug="user-1-secret-notes",
            source="uploaded",
            is_private=True,
            is_published=True,
            created_by=self.user1_id,
        )
        self.db.add(c)
        self.db.commit()

        # Unauthenticated request to /api/courses
        resp = self.client.get("/api/courses")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        slugs = [item["slug"] for item in items]
        self.assertNotIn("user-1-secret-notes", slugs)

    def test_security_stranger_cannot_access_private_course(self):
        # Course owned by user1
        c = Course(
            id=uuid.uuid4(),
            title="User 1 Private Course",
            slug="user-1-private-course",
            source="uploaded",
            is_private=True,
            is_published=True,
            created_by=self.user1_id,
        )
        self.db.add(c)
        self.db.commit()

        # 1. Unauthenticated -> 404
        resp = self.client.get("/api/courses/user-1-private-course")
        self.assertEqual(resp.status_code, 404)

        # 2. Authenticated as user2 (stranger) -> 404
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user2_id),
            "email": self.user2.email,
            "role": "student",
        }
        resp2 = self.client.get(
            "/api/courses/user-1-private-course",
            headers={"Authorization": "Bearer fake_token"},
        )
        self.assertEqual(resp2.status_code, 404)

        # 3. Authenticated as creator (user1) -> 200
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user1_id),
            "email": self.user1.email,
            "role": "student",
        }
        resp3 = self.client.get(
            "/api/courses/user-1-private-course",
            headers={"Authorization": "Bearer fake_token"},
        )
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.json()["title"], "User 1 Private Course")

    def test_security_stranger_cannot_access_private_lesson(self):
        c = Course(
            id=uuid.uuid4(),
            title="Secret Course",
            slug="secret-course",
            is_private=True,
            is_published=True,
            created_by=self.user1_id,
        )
        l = Lesson(
            id=uuid.uuid4(),
            course_id=c.id,
            title="Secret Lesson",
            order_index=1,
            content_md="Confidential information",
            topic_tags=["sql.basics"],
        )
        self.db.add_all([c, l])
        self.db.commit()

        # User2 tries to read user1's private lesson -> 404
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user2_id),
            "email": self.user2.email,
            "role": "student",
        }
        resp = self.client.get(f"/api/lessons/{l.id}", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp.status_code, 404)

        # User1 (creator) reads their private lesson -> 200
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user1_id),
            "email": self.user1.email,
            "role": "student",
        }
        resp2 = self.client.get(f"/api/lessons/{l.id}", headers={"Authorization": "Bearer t"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["title"], "Secret Lesson")

    def test_creator_can_edit_course_and_lesson_titles(self):
        c = Course(
            id=uuid.uuid4(),
            title="Initial Title",
            slug="initial-title",
            is_private=True,
            created_by=self.user1_id,
        )
        l = Lesson(
            id=uuid.uuid4(),
            course_id=c.id,
            title="Initial Lesson",
            order_index=1,
            content_md="Content",
            topic_tags=["sql.basics"],
        )
        self.db.add_all([c, l])
        self.db.commit()

        # Creator updates course title
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user1_id),
            "email": self.user1.email,
            "role": "student",
        }
        patch_course = self.client.patch(
            f"/api/courses/{c.id}",
            json={"title": "Updated Course Title"},
            headers={"Authorization": "Bearer t"},
        )
        self.assertEqual(patch_course.status_code, 200)
        self.assertEqual(patch_course.json()["title"], "Updated Course Title")

        # Creator updates lesson title
        patch_lesson = self.client.patch(
            f"/api/courses/{c.id}/lessons/{l.id}",
            json={"title": "Updated Lesson Title"},
            headers={"Authorization": "Bearer t"},
        )
        self.assertEqual(patch_lesson.status_code, 200)
        self.assertEqual(patch_lesson.json()["title"], "Updated Lesson Title")

        # Stranger attempts to update lesson title -> 403
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user2_id),
            "email": self.user2.email,
            "role": "student",
        }
        unauthorized_patch = self.client.patch(
            f"/api/courses/{c.id}/lessons/{l.id}",
            json={"title": "Hacked Lesson Title"},
            headers={"Authorization": "Bearer t"},
        )
        self.assertEqual(unauthorized_patch.status_code, 403)


if __name__ == "__main__":
    unittest.main()
