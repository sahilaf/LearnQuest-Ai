"""Run a student's SQL safely and grade it against a reference solution.

OWNER: Member 1. Consumed by routers/practice.py.

This executes code a student typed. It is safe because of WHERE it runs, not
because of any attempt to inspect the query:

  - Every run gets a brand-new in-memory SQLite database, seeded only with that
    test case's tables. It has no connection to the application's Postgres,
    no rows but the seed, and disappears when the run ends. There is nothing
    there to steal or break.
  - An authorizer rejects everything a SELECT does not need. ATTACH matters
    most: it is the one statement that can reach outside an in-memory
    database, by opening a file on disk.
  - A progress handler aborts anything that runs too long, so a cross join of
    two big tables cannot pin a worker.
  - `execute()` runs exactly one statement, so `SELECT 1; DROP ...` fails
    before anything executes rather than after the first half does.
  - Rows are capped, so a query cannot return a million rows to be diffed.

Grading runs the reference solution against the same seed and compares result
sets. Expected output is therefore never hand-written, and a test case cannot
disagree with its own answer key.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from decimal import Decimal
from typing import Any

logger = logging.getLogger("learnquest.sqlrunner")

TIMEOUT_SECONDS = 2.0
MAX_ROWS = 500
MAX_QUERY_CHARS = 5000

# Authorizer action codes (stable SQLite constants; exposed on the module).
_ALLOWED = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    # A CTE is compiled as a recursive select.
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


class QueryError(Exception):
    """The student's query could not run. The message is shown to them."""


def _authorizer(action, arg1, arg2, db_name, trigger):
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


def _normalise_value(value: Any) -> Any:
    """Make equal answers compare equal.

    Floats are rounded so `80.0` and `80` and `79.99999999` do not fail a
    correct aggregate. Strings are trimmed because trailing whitespace is never
    what a student got wrong.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        return int(number) if number.is_integer() else round(number, 2)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").strip()
    text = str(value).strip()
    # Numbers stored as text in the seed should still match numeric answers.
    try:
        number = float(text)
        return int(number) if number.is_integer() else round(number, 2)
    except ValueError:
        return text


def _run(setup_sql: str, query: str, *, authorize: bool) -> list[tuple]:
    conn = sqlite3.connect(":memory:")
    try:
        # The seed is ours and trusted, so it runs before any restriction.
        conn.executescript(setup_sql)

        if authorize:
            conn.set_authorizer(_authorizer)

        deadline = time.monotonic() + TIMEOUT_SECONDS

        def _progress():
            # Non-zero aborts the statement.
            return 1 if time.monotonic() > deadline else 0

        conn.set_progress_handler(_progress, 1000)

        cursor = conn.execute(query)
        rows = cursor.fetchmany(MAX_ROWS + 1)
        if len(rows) > MAX_ROWS:
            raise QueryError(f"Your query returned more than {MAX_ROWS} rows.")
        return rows
    except (sqlite3.Error, sqlite3.Warning) as exc:
        # Mapped by message, not by class: the authorizer raises a bare
        # DatabaseError, a timeout an OperationalError and a second statement a
        # ProgrammingError (or Warning on older Pythons). Catching one subclass
        # leaked SQLite's raw "not authorized" to students.
        raise QueryError(_friendly(str(exc))) from exc
    finally:
        conn.close()


def _friendly(message: str) -> str:
    """Translate SQLite's wording into something a student can act on."""
    lowered = message.lower()
    if "interrupted" in lowered:
        return f"Your query took longer than {TIMEOUT_SECONDS:g}s and was stopped."
    if "not authorized" in lowered:
        return "Only SELECT queries are allowed here - no changes to the tables."
    if "one statement at a time" in lowered:
        return "Submit a single SELECT statement."
    # Syntax errors and unknown columns are already in useful words.
    return message


def _clean(query: str) -> str:
    text = (query or "").strip()
    # One trailing semicolon is normal style, not a second statement.
    text = re.sub(r";\s*$", "", text)
    if not text:
        raise QueryError("Write a query first.")
    if len(text) > MAX_QUERY_CHARS:
        raise QueryError("That query is too long.")
    return text


def _format(rows: list[tuple]) -> str:
    if not rows:
        return "(no rows)"
    shown = rows[:12]
    lines = [" | ".join("NULL" if v is None else str(v) for v in row) for row in shown]
    if len(rows) > len(shown):
        lines.append(f"... {len(rows) - len(shown)} more row(s)")
    return "\n".join(lines)


def grade_case(
    *,
    setup_sql: str,
    reference_sql: str,
    student_sql: str,
    order_matters: bool,
) -> dict[str, Any]:
    """Grade one test case. Never raises for anything the student did."""
    started = time.perf_counter()

    try:
        expected = _run(setup_sql, reference_sql, authorize=False)
    except Exception as exc:  # noqa: BLE001 - a broken problem, not a wrong answer
        logger.error("Reference solution failed on its own test case: %s", exc)
        return {
            "status": "error",
            "error": "This test case is misconfigured. It is not your fault.",
            "expected_rows": None,
            "actual_rows": None,
            "execution_ms": 0,
        }

    try:
        actual = _run(setup_sql, _clean(student_sql), authorize=True)
    except QueryError as exc:
        return {
            "status": "error",
            "error": str(exc),
            "expected_rows": expected,
            "actual_rows": None,
            "execution_ms": int((time.perf_counter() - started) * 1000),
        }

    expected_norm = [tuple(_normalise_value(v) for v in row) for row in expected]
    actual_norm = [tuple(_normalise_value(v) for v in row) for row in actual]

    if order_matters:
        passed = expected_norm == actual_norm
    else:
        # Compare as multisets. A correct query without ORDER BY must not fail
        # because the engine happened to return rows in another order.
        passed = sorted(map(repr, expected_norm)) == sorted(map(repr, actual_norm))

    return {
        "status": "passed" if passed else "failed",
        "error": None,
        "expected_rows": expected,
        "actual_rows": actual,
        "execution_ms": int((time.perf_counter() - started) * 1000),
    }


def format_rows(rows: list[tuple] | None) -> str | None:
    return None if rows is None else _format(rows)
