"""SQL practice problems, graded by running them. OWNER: M2 (UI) / M1 (runner).

Shapes match `frontend/src/api/practice.js` field for field, so the existing
PracticeList and ProblemViewer work unchanged.

What the client never sees: the reference solution (it is the answer) and the
setup SQL of any test case (it would let a student fit their query to the hidden
cases). Hidden cases report pass or fail, never their data.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser

logger = logging.getLogger("learnquest.practice")

router = APIRouter(prefix="/api/practice", tags=["practice"])

# A skill counts as verified once this many distinct problems in it are solved,
# or all of them if there are fewer.
REQUIRED_TO_VERIFY = 2


class SubmitRequest(BaseModel):
    code: str = Field(..., max_length=5000)


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return db


def _user_uuid(user: Any) -> uuid.UUID:
    try:
        return uuid.UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user.") from err


def _labels(db: Session) -> dict[str, str]:
    from app.models.ai import Topic

    return {t.tag: t.label for t in db.query(Topic).all()}


def _load_problem(db: Session, ref: str):
    """By id or by slug - the UI links with either."""
    from app.models.practice import PracticeProblem

    query = db.query(PracticeProblem)
    try:
        problem = query.filter(PracticeProblem.id == uuid.UUID(str(ref))).first()
    except ValueError:
        problem = None
    if problem is None:
        problem = query.filter(PracticeProblem.slug == str(ref)).first()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")
    return problem


def _stats(db: Session, user_uuid: uuid.UUID) -> tuple[dict, dict, dict]:
    """(per-problem status, acceptance, totals) in three grouped queries.

    Not per problem: the list is the page students land on, and a query per row
    against a remote database is exactly the N+1 fixed elsewhere in this repo.
    """
    from app.models.practice import PracticeSubmission

    mine = (
        db.query(
            PracticeSubmission.problem_id,
            func.max(func.cast(PracticeSubmission.all_passed, Integer)),
        )
        .filter(PracticeSubmission.user_id == user_uuid)
        .group_by(PracticeSubmission.problem_id)
        .all()
    )
    status_by_problem = {pid: ("solved" if best else "attempted") for pid, best in mine}

    totals = (
        db.query(
            PracticeSubmission.problem_id,
            func.count(PracticeSubmission.id),
            func.sum(func.cast(PracticeSubmission.all_passed, Integer)),
        )
        .group_by(PracticeSubmission.problem_id)
        .all()
    )
    total_by_problem = {pid: int(n or 0) for pid, n, _ in totals}
    accepted_by_problem = {pid: int(ok or 0) for pid, _, ok in totals}
    return status_by_problem, total_by_problem, accepted_by_problem


def _summary(problem, labels, status_by, total_by, accepted_by) -> dict[str, Any]:
    total = total_by.get(problem.id, 0)
    accepted = accepted_by.get(problem.id, 0)
    return {
        "id": str(problem.id),
        "slug": problem.slug,
        "title": problem.title,
        "skill_id": problem.topic_tag,
        "skill_name": labels.get(problem.topic_tag, problem.topic_tag),
        "topic_tag": problem.topic_tag,
        "difficulty": problem.difficulty,
        "status": status_by.get(problem.id, "unsolved"),
        # A real rate, or an honest dash - never an invented percentage.
        "acceptance_rate": f"{100 * accepted / total:.1f}%" if total else "—",
        "total_submissions": total,
    }


@router.get("/problems")
def list_problems(
    user: CurrentUser,
    db: Session | None = Depends(get_db),
    skill: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
) -> dict[str, Any]:
    from app.models.practice import PracticeProblem

    database = _require_db(db)
    user_uuid = _user_uuid(user)

    query = database.query(PracticeProblem)
    if skill:
        query = query.filter(PracticeProblem.topic_tag == skill)
    if difficulty:
        query = query.filter(PracticeProblem.difficulty == difficulty)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            PracticeProblem.title.ilike(like) | PracticeProblem.statement_md.ilike(like)
        )

    problems = query.order_by(PracticeProblem.position).all()
    labels = _labels(database)
    status_by, total_by, accepted_by = _stats(database, user_uuid)

    items = []
    for problem in problems:
        item = _summary(problem, labels, status_by, total_by, accepted_by)
        item["statement_md"] = problem.statement_md
        items.append(item)
    return {"items": items, "total": len(items)}


@router.get("/problems/{problem_ref}")
def get_problem(
    problem_ref: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    from app.services.sql_runner import _run, format_rows

    database = _require_db(db)
    user_uuid = _user_uuid(user)
    problem = _load_problem(database, problem_ref)

    labels = _labels(database)
    status_by, total_by, accepted_by = _stats(database, user_uuid)
    data = _summary(problem, labels, status_by, total_by, accepted_by)

    cases = []
    for case in problem.test_cases:
        entry = {"id": str(case.id), "title": case.title, "is_hidden": case.is_hidden}
        if not case.is_hidden:
            # Computed from the reference, so it cannot disagree with grading.
            try:
                entry["expected_output"] = format_rows(
                    _run(case.setup_sql, problem.reference_sql, authorize=False)
                )
            except Exception:  # noqa: BLE001
                entry["expected_output"] = None
        cases.append(entry)

    data.update(
        {
            "statement_md": problem.statement_md,
            "input_format": problem.input_format,
            "output_format": problem.output_format,
            "constraints": problem.constraints or [],
            "examples": problem.examples or [],
            "starter_code": problem.starter_code,
            "dialect": "SQLite",
            "test_cases": cases,
        }
    )
    return data


@router.post("/problems/{problem_ref}/submit")
def submit(
    problem_ref: str,
    body: SubmitRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Run every test case against the student's query and record the attempt."""
    from app.models.practice import PracticeSubmission
    from app.services.sql_runner import format_rows, grade_case

    database = _require_db(db)
    user_uuid = _user_uuid(user)
    problem = _load_problem(database, problem_ref)

    if not body.code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Write a query first.")

    results = []
    for case in problem.test_cases:
        outcome = grade_case(
            setup_sql=case.setup_sql,
            reference_sql=problem.reference_sql,
            student_sql=body.code,
            order_matters=problem.order_matters,
        )
        hidden = case.is_hidden
        results.append(
            {
                "test_case_id": str(case.id),
                "title": case.title,
                "is_hidden": hidden,
                "status": outcome["status"],
                # Hidden cases say pass or fail and nothing else; showing their
                # data would let a student fit the query to the answer.
                "expected_output": "(Hidden)" if hidden else format_rows(outcome["expected_rows"]),
                "actual_output": (
                    "(Hidden)" if hidden and outcome["status"] != "error"
                    else outcome["error"] or format_rows(outcome["actual_rows"])
                ),
                "error": outcome["error"],
                "execution_ms": outcome["execution_ms"],
            }
        )

    passed = sum(1 for r in results if r["status"] == "passed")
    all_passed = bool(results) and passed == len(results)

    submission = PracticeSubmission(
        user_id=user_uuid,
        problem_id=problem.id,
        code=body.code,
        all_passed=all_passed,
        passed_cases=passed,
        total_cases=len(results),
        results=[{k: v for k, v in r.items() if k != "actual_output"} for r in results],
    )
    database.add(submission)

    # A passing solution is evidence about the topic, so it feeds the same
    # mastery model the quizzes do.
    try:
        from app.services.mastery import update_mastery

        update_mastery(database, user_uuid, problem.topic_tag, 1 if all_passed else 0, 1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not update mastery from practice: %s", exc)

    database.commit()
    database.refresh(submission)

    return {
        "attempt_id": str(submission.id),
        "problem_id": str(problem.id),
        "submitted_at": (submission.created_at or datetime.now(timezone.utc)).isoformat(),
        "all_passed": all_passed,
        "passed_test_cases": passed,
        "total_test_cases": len(results),
        "test_case_results": results,
        "skill_verified": _skill_verified(database, user_uuid, problem.topic_tag),
    }


def _skill_verified(db: Session, user_uuid: uuid.UUID, topic_tag: str) -> bool:
    from app.models.practice import PracticeProblem, PracticeSubmission

    available = db.query(PracticeProblem).filter(PracticeProblem.topic_tag == topic_tag).count()
    solved = (
        db.query(func.count(func.distinct(PracticeSubmission.problem_id)))
        .join(PracticeProblem, PracticeProblem.id == PracticeSubmission.problem_id)
        .filter(
            PracticeSubmission.user_id == user_uuid,
            PracticeSubmission.all_passed.is_(True),
            PracticeProblem.topic_tag == topic_tag,
        )
        .scalar()
    ) or 0
    return solved >= min(REQUIRED_TO_VERIFY, available) and available > 0


@router.get("/skills")
def skills(user: CurrentUser, db: Session | None = Depends(get_db)) -> dict[str, Any]:
    """Verification status for every topic that has practice problems."""
    from app.models.practice import PracticeProblem, PracticeSubmission

    database = _require_db(db)
    user_uuid = _user_uuid(user)
    labels = _labels(database)

    available = dict(
        database.query(PracticeProblem.topic_tag, func.count(PracticeProblem.id))
        .group_by(PracticeProblem.topic_tag)
        .all()
    )
    solved = dict(
        database.query(PracticeProblem.topic_tag, func.count(func.distinct(PracticeSubmission.problem_id)))
        .join(PracticeProblem, PracticeProblem.id == PracticeSubmission.problem_id)
        .filter(PracticeSubmission.user_id == user_uuid, PracticeSubmission.all_passed.is_(True))
        .group_by(PracticeProblem.topic_tag)
        .all()
    )

    items = []
    for tag in sorted(available):
        required = min(REQUIRED_TO_VERIFY, available[tag])
        passed = int(solved.get(tag, 0))
        items.append(
            {
                "id": tag,
                "name": labels.get(tag, tag),
                "required_to_verify": required,
                "passed_count": passed,
                "verified": passed >= required,
            }
        )
    return {"items": items}
