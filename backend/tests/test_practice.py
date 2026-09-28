"""SQL practice: the sandbox, the grader, and what the API reveals.

The sandbox tests come first because this code runs what a student typed. Each
one is an attack a curious student will actually try.

The grader tests carry the other half. Practice used to have no backend at all;
the frontend "graded" by passing any code longer than 15 characters and reported
a randomised runtime so it looked real. These tests are what stop that coming
back in a quieter form.
"""

from __future__ import annotations

import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ai import Topic, TopicMastery
from app.models.practice import PracticeProblem, PracticeSubmission, PracticeTestCase
from app.models.user import User
from app.services.sql_runner import grade_case

SETUP = """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT, amount REAL);
INSERT INTO customers VALUES (1,'Alice'),(2,'Bob');
INSERT INTO orders VALUES (10,1,50),(11,1,30);"""
REF = (
    "SELECT c.name, COALESCE(SUM(o.amount),0) FROM customers c "
    "LEFT JOIN orders o ON o.customer_id=c.customer_id GROUP BY c.customer_id"
)


def _grade(sql, order=False):
    return grade_case(setup_sql=SETUP, reference_sql=REF, student_sql=sql, order_matters=order)


class TestSandbox(unittest.TestCase):
    """Every one of these is something a student will try."""

    def test_attach_cannot_reach_the_filesystem(self) -> None:
        """ATTACH is the one statement that escapes an in-memory database."""
        r = _grade("ATTACH DATABASE 'C:/anything.db' AS x")
        self.assertEqual(r["status"], "error")
        self.assertIn("Only SELECT", r["error"])

    def test_writes_are_refused(self) -> None:
        for sql in (
            "DROP TABLE customers",
            "INSERT INTO customers VALUES (9,'x')",
            "UPDATE customers SET name='x'",
            "DELETE FROM customers",
            "CREATE TABLE t(a INT)",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(_grade(sql)["status"], "error")

    def test_pragma_is_refused(self) -> None:
        self.assertEqual(_grade("PRAGMA table_info(customers)")["status"], "error")

    def test_a_second_statement_never_runs(self) -> None:
        """Rejected before execution, not after the first half has run."""
        r = _grade("SELECT 1; DROP TABLE customers")
        self.assertEqual(r["status"], "error")
        self.assertIn("single SELECT", r["error"])

    def test_a_runaway_query_is_stopped(self) -> None:
        r = _grade(
            "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) "
            "SELECT count(*) FROM r"
        )
        self.assertEqual(r["status"], "error")
        self.assertIn("stopped", r["error"])

    def test_errors_are_in_words_a_student_can_act_on(self) -> None:
        """SQLite's raw "not authorized" used to leak through."""
        self.assertNotEqual(_grade("DROP TABLE customers")["error"], "not authorized")


class TestGrading(unittest.TestCase):
    def test_a_correct_query_passes(self) -> None:
        self.assertEqual(_grade(REF)["status"], "passed")

    def test_row_order_is_ignored_when_it_does_not_matter(self) -> None:
        self.assertEqual(_grade(REF + " ORDER BY c.name DESC")["status"], "passed")

    def test_row_order_is_enforced_when_it_does(self) -> None:
        r = grade_case(
            setup_sql=SETUP,
            reference_sql=REF + " ORDER BY c.name",
            student_sql=REF + " ORDER BY c.name DESC",
            order_matters=True,
        )
        self.assertEqual(r["status"], "failed")

    def test_a_wrong_query_fails(self) -> None:
        """INNER JOIN drops Bob, who has no orders - a real, common mistake."""
        self.assertEqual(_grade(REF.replace("LEFT JOIN", "JOIN"))["status"], "failed")

    def test_a_long_wrong_query_still_fails(self) -> None:
        """The old frontend fallback passed anything over 15 characters."""
        self.assertEqual(
            _grade("SELECT name, 999999 FROM customers WHERE 1=1")["status"], "failed"
        )

    def test_numbers_compare_by_value(self) -> None:
        self.assertEqual(
            _grade(
                "SELECT c.name, COALESCE(SUM(o.amount),0.0) FROM customers c "
                "LEFT JOIN orders o ON o.customer_id=c.customer_id GROUP BY c.customer_id"
            )["status"],
            "passed",
        )

    def test_a_trailing_semicolon_is_normal_style(self) -> None:
        self.assertEqual(_grade(REF + ";")["status"], "passed")

    def test_the_seeded_hidden_cases_catch_the_naive_answer(self) -> None:
        """Hidden cases exist to catch what the visible one lets through."""
        from app.seed.practice_problems import PROBLEMS

        problem = next(p for p in PROBLEMS if p["slug"] == "customer-spend-summary")
        naive = (
            "SELECT c.customer_id, c.name, SUM(o.amount) AS total_spent FROM customers c "
            "JOIN orders o ON o.customer_id=c.customer_id GROUP BY c.customer_id "
            "ORDER BY total_spent DESC"
        )
        results = {
            hidden: grade_case(
                setup_sql=setup,
                reference_sql=problem["reference_sql"],
                student_sql=naive,
                order_matters=True,
            )["status"]
            for _title, hidden, setup in problem["cases"]
        }
        # Passes what it can see, fails what it cannot. That is the point.
        self.assertEqual(results[False], "passed")
        self.assertEqual(results[True], "failed")

    def test_every_seeded_reference_runs(self) -> None:
        from app.seed.practice_problems import validate

        self.assertEqual(validate(), [])


class TestPracticeAPI(unittest.TestCase):
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
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.deps import get_current_user
        from app.main import app

        self.db = self.Session()
        self.user_id = uuid.uuid4()
        self.db.add(User(id=self.user_id, email=f"{self.user_id.hex[:8]}@t.local", full_name="T"))
        self.db.add(Topic(tag="dbms.sql_joins", label="SQL joins", subject="dbms", is_active=True))
        self.problem = PracticeProblem(
            slug="spend",
            title="Spend",
            topic_tag="dbms.sql_joins",
            difficulty="easy",
            statement_md="Sum it.",
            constraints=[],
            examples=[],
            starter_code="SELECT",
            reference_sql=REF,
            order_matters=False,
        )
        self.db.add(self.problem)
        self.db.flush()
        self.db.add_all(
            [
                PracticeTestCase(problem_id=self.problem.id, title="visible", is_hidden=False,
                                 setup_sql=SETUP, position=0),
                PracticeTestCase(problem_id=self.problem.id, title="hidden", is_hidden=True,
                                 setup_sql=SETUP, position=1),
            ]
        )
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: {
            "id": str(self.user_id), "email": "t@local", "role": "student"
        }
        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.db.rollback()
        for model in (PracticeSubmission, PracticeTestCase, PracticeProblem, TopicMastery, Topic, User):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()

    def test_the_answer_key_never_reaches_the_client(self) -> None:
        body = self.client.get(f"/api/practice/problems/{self.problem.id}").json()
        text = str(body)
        self.assertNotIn("reference_sql", body)
        self.assertNotIn("COALESCE", text)          # the reference solution
        self.assertNotIn("CREATE TABLE", text)      # any test case's seed
        hidden = next(c for c in body["test_cases"] if c["is_hidden"])
        self.assertNotIn("expected_output", hidden)

    def test_a_problem_is_found_by_slug_too(self) -> None:
        self.assertEqual(self.client.get("/api/practice/problems/spend").status_code, 200)

    def test_submitting_a_correct_query_passes_and_is_recorded(self) -> None:
        r = self.client.post(f"/api/practice/problems/{self.problem.id}/submit", json={"code": REF})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["all_passed"])
        self.assertEqual(body["passed_test_cases"], 2)
        self.assertEqual(self.db.query(PracticeSubmission).count(), 1)

    def test_hidden_results_do_not_leak_their_data(self) -> None:
        body = self.client.post(
            f"/api/practice/problems/{self.problem.id}/submit",
            json={"code": REF.replace("LEFT JOIN", "JOIN")},
        ).json()
        hidden = next(c for c in body["test_case_results"] if c["is_hidden"])
        self.assertEqual(hidden["expected_output"], "(Hidden)")
        self.assertEqual(hidden["actual_output"], "(Hidden)")

    def test_a_pass_moves_mastery(self) -> None:
        self.client.post(f"/api/practice/problems/{self.problem.id}/submit", json={"code": REF})
        self.assertIsNotNone(
            self.db.query(TopicMastery).filter(TopicMastery.topic_tag == "dbms.sql_joins").first()
        )

    def test_status_and_skills_reflect_real_submissions(self) -> None:
        listed = self.client.get("/api/practice/problems").json()["items"][0]
        self.assertEqual(listed["status"], "unsolved")
        self.assertEqual(listed["acceptance_rate"], "—")  # honest, not invented

        self.client.post(f"/api/practice/problems/{self.problem.id}/submit", json={"code": REF})
        listed = self.client.get("/api/practice/problems").json()["items"][0]
        self.assertEqual(listed["status"], "solved")
        self.assertEqual(listed["acceptance_rate"], "100.0%")

        skill = self.client.get("/api/practice/skills").json()["items"][0]
        self.assertTrue(skill["verified"])  # one problem available, one solved

    def test_blank_code_is_refused(self) -> None:
        r = self.client.post(f"/api/practice/problems/{self.problem.id}/submit", json={"code": "  "})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
