"""Seed practice quizzes for flagship lessons.

OWNER: Member 2 (Learning Management).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.quiz import Question, Quiz

logger = logging.getLogger("learnquest.seed.quizzes")

QUIZ_1_ID = uuid.UUID("33333333-3333-3333-3333-333333330001")
QUIZ_2_ID = uuid.UUID("33333333-3333-3333-3333-333333330002")
QUIZ_3_ID = uuid.UUID("33333333-3333-3333-3333-333333330003")

LESSON_1_ID = uuid.UUID("22222222-2222-2222-2222-222222220001")
LESSON_2_ID = uuid.UUID("22222222-2222-2222-2222-222222220002")
LESSON_3_ID = uuid.UUID("22222222-2222-2222-2222-222222220003")
COURSE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def seed_quizzes(db: Session) -> None:
    """Seed flagship quizzes and questions if not present."""
    now = datetime.now(timezone.utc)

    # 1. Quiz for Lesson 1: Relational Model & Keys
    q1 = db.query(Quiz).filter(Quiz.id == QUIZ_1_ID).first()
    if not q1:
        q1 = Quiz(
            id=QUIZ_1_ID,
            lesson_id=LESSON_1_ID,
            course_id=COURSE_ID,
            title="Relational Model & Key Concepts Mastery Quiz",
            source="manual",
            difficulty="beginner",
            topic_tags=["dbms.er_model"],
            created_at=now,
        )
        db.add(q1)

        questions_1 = [
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440101"),
                quiz_id=QUIZ_1_ID,
                type="mcq",
                prompt="What is a Candidate Key in relational database theory?",
                options=[
                    "Any combination of attributes that uniquely identifies a row",
                    "A minimal superkey with no unnecessary attributes",
                    "A foreign key that references a parent table",
                    "The primary key chosen specifically for clustering index",
                ],
                correct_answer="A minimal superkey with no unnecessary attributes",
                explanation="A candidate key is defined as a minimal superkey: removing any attribute from it breaks its uniqueness guarantee.",
                topic_tag="dbms.er_model",
                difficulty="beginner",
                order_index=1,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440102"),
                quiz_id=QUIZ_1_ID,
                type="true_false",
                prompt="A foreign key column MUST have the exact same column name as the primary key column it references.",
                options=["True", "False"],
                correct_answer="False",
                explanation="Column names can differ entirely (e.g. orders.customer_uuid referencing customers.id); only data types and domains must match.",
                topic_tag="dbms.er_model",
                difficulty="beginner",
                order_index=2,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440103"),
                quiz_id=QUIZ_1_ID,
                type="fill_blank",
                prompt="A foreign key that references a deleted row will automatically remove child records if configured with ON DELETE ______.",
                options=None,
                correct_answer="CASCADE",
                explanation="The CASCADE option propagates row deletions from the referenced table to child tables.",
                topic_tag="dbms.er_model",
                difficulty="intermediate",
                order_index=3,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440104"),
                quiz_id=QUIZ_1_ID,
                type="short_answer",
                prompt="What constraint ensures that foreign key values always point to valid, existing primary keys in the referenced relation?",
                options=None,
                correct_answer="Referential Integrity",
                explanation="Referential integrity dictates that foreign keys must reference valid primary key values or be NULL.",
                topic_tag="dbms.er_model",
                difficulty="intermediate",
                order_index=4,
            ),
        ]
        for q in questions_1:
            db.add(q)
        logger.info("Seeded Quiz 1 with %d questions.", len(questions_1))

    # 2. Quiz for Lesson 3: SQL Joins Demystified
    q3 = db.query(Quiz).filter(Quiz.id == QUIZ_3_ID).first()
    if not q3:
        q3 = Quiz(
            id=QUIZ_3_ID,
            lesson_id=LESSON_3_ID,
            course_id=COURSE_ID,
            title="SQL Joins In-Depth Practice Quiz",
            source="manual",
            difficulty="intermediate",
            topic_tags=["dbms.sql_joins"],
            created_at=now,
        )
        db.add(q3)

        questions_3 = [
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440301"),
                quiz_id=QUIZ_3_ID,
                type="mcq",
                prompt="What does an INNER JOIN return when joining Table A and Table B?",
                options=[
                    "All rows from both tables combined",
                    "Only rows that have matching values in both tables according to the join condition",
                    "All rows from Table A and only matching rows from Table B",
                    "The cartesian product of both tables without any filtering",
                ],
                correct_answer="Only rows that have matching values in both tables according to the join condition",
                explanation="An INNER JOIN selects records that have matching values in both tables, discarding unmatched rows.",
                topic_tag="dbms.sql_joins",
                difficulty="beginner",
                order_index=1,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440302"),
                quiz_id=QUIZ_3_ID,
                type="true_false",
                prompt="In a LEFT JOIN, unmatched rows from the left table are discarded from the final result.",
                options=["True", "False"],
                correct_answer="False",
                explanation="A LEFT JOIN preserves ALL rows from the left table; columns from the right table are filled with NULL when no match exists.",
                topic_tag="dbms.sql_joins",
                difficulty="intermediate",
                order_index=2,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440303"),
                quiz_id=QUIZ_3_ID,
                type="fill_blank",
                prompt="When no match is found for a row in an OUTER JOIN, missing right-table columns are populated with the value ______.",
                options=None,
                correct_answer="NULL",
                explanation="Standard SQL populates unmatched outer join rows with NULL values.",
                topic_tag="dbms.sql_joins",
                difficulty="beginner",
                order_index=3,
            ),
            Question(
                id=uuid.UUID("44444444-4444-4444-4444-444444440304"),
                quiz_id=QUIZ_3_ID,
                type="short_answer",
                prompt="What type of join returns all rows from the Cartesian product where no join condition or ON clause is provided?",
                options=None,
                correct_answer="CROSS JOIN",
                explanation="A CROSS JOIN produces the Cartesian product of rows from both tables.",
                topic_tag="dbms.sql_joins",
                difficulty="intermediate",
                order_index=4,
            ),
        ]
        for q in questions_3:
            db.add(q)
        logger.info("Seeded Quiz 3 with %d questions.", len(questions_3))

    db.commit()
