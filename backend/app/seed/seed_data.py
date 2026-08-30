"""Seed the database with demo content.

OWNER: Member 3. Run with:  python -m app.seed.seed_data

This is the highest-leverage deliverable of week 1 (plan.md 8.1, day 4):
Member 1 cannot test the tutor and Member 2 cannot test the lesson viewer
against an empty database.

Target: 3 courses x 5 lessons with REAL markdown content and REAL topic_tags.
Every member contributes fixtures for their own tables here.
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("learnquest.seed")

# Agree this vocabulary as a team in week 1 (plan.md 3.1), then use it everywhere.
TOPIC_VOCABULARY = [
    "python.basics",
    "python.loops",
    "python.functions",
    "python.oop",
    "dbms.er_model",
    "dbms.normalization",
    "dbms.sql_joins",
    "dbms.transactions",
    "web.html_css",
    "web.javascript",
    "web.react",
    "web.rest_api",
]


def seed_courses(db) -> None:
    """TODO(M3): 3 courses x 5 lessons, real markdown, tags from TOPIC_VOCABULARY."""
    raise NotImplementedError("TODO(M3): week 1 day 4")


def seed_badges(db) -> None:
    """TODO(M4): ~15 badges with JSONB criteria (plan.md 9.4)."""
    raise NotImplementedError("TODO(M4): week 2")


def seed_challenges(db) -> None:
    """TODO(M4): the daily challenge template pool (plan.md 9.5)."""
    raise NotImplementedError("TODO(M4): week 3")


def main() -> None:
    from app.database import get_session_factory

    db = get_session_factory()()
    try:
        seed_courses(db)
        seed_badges(db)
        seed_challenges(db)
        db.commit()
        logger.info("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
