"""Seed the database with demo content.

OWNER: Member 3. Run with:  python -m app.seed.seed_data

This is the highest-leverage deliverable of week 1 (plan.md §8.1, day 4):
Member 1 cannot test the tutor and Member 2 cannot test the lesson viewer
against an empty database.

Target: ONE course done properly (6–8 real lessons) with REAL markdown content
and REAL topic_tags. SQL/DBMS is the recommended subject.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.course import Course, Enrollment, Lesson
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("learnquest.seed")

# Controlled vocabulary agreed in week 1 (plan.md §3.1)
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

DEMO_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_STUDENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


from sqlalchemy import text


def seed_users(db: Session) -> tuple[User | None, User | None]:
    """Seed demo admin and student users."""
    now = datetime.now(timezone.utc)
    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

    # In PostgreSQL, auth.users must contain the ID before public.users can reference it
    if is_postgres:
        try:
            db.execute(
                text(
                    """
                INSERT INTO auth.users (
                    id, aud, role, email, encrypted_password, email_confirmed_at,
                    created_at, updated_at, raw_app_meta_data, raw_user_meta_data
                ) VALUES 
                (
                    '00000000-0000-0000-0000-000000000001', 'authenticated', 'authenticated',
                    'admin@learnquest.ai', '$2a$10$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012',
                    NOW(), NOW(), NOW(), '{"provider":"email"}', '{"full_name":"Alex Mercer"}'
                ),
                (
                    '00000000-0000-0000-0000-000000000002', 'authenticated', 'authenticated',
                    'student@learnquest.ai', '$2a$10$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ012',
                    NOW(), NOW(), NOW(), '{"provider":"email"}', '{"full_name":"Sarah Chen"}'
                )
                ON CONFLICT (id) DO NOTHING;
            """
                )
            )
            db.commit()
        except Exception as e:
            logger.warning("Pre-seeding auth.users skipped or not permitted: %s", e)
            db.rollback()

    admin = db.query(User).filter(User.id == DEMO_ADMIN_ID).first()
    student = db.query(User).filter(User.id == DEMO_STUDENT_ID).first()

    try:
        if not admin:
            admin = User(
                id=DEMO_ADMIN_ID,
                email="admin@learnquest.ai",
                full_name="Alex Mercer (Admin)",
                role="admin",
                preferences={"tutor_tone": "concise", "difficulty_pref": "advanced", "daily_goal_minutes": 30},
                created_at=now,
                last_login_at=now,
            )
            db.add(admin)
            logger.info("Created demo admin user: %s", admin.email)

        if not student:
            student = User(
                id=DEMO_STUDENT_ID,
                email="student@learnquest.ai",
                full_name="Sarah Chen (Student)",
                role="student",
                preferences={"tutor_tone": "encouraging", "difficulty_pref": "intermediate", "daily_goal_minutes": 20},
                created_at=now,
                last_login_at=now,
            )
            db.add(student)
            logger.info("Created demo student user: %s", student.email)

        db.commit()
    except Exception as e:
        logger.warning("Could not seed public.users (%s). Proceeding with course content.", e)
        db.rollback()
        admin = db.query(User).filter(User.id == DEMO_ADMIN_ID).first()
        student = db.query(User).filter(User.id == DEMO_STUDENT_ID).first()

    return admin, student


def seed_courses(db: Session) -> Course:
    """Seed ONE course done properly: 7 real lessons with comprehensive markdown and tags."""
    admin, student = seed_users(db)
    admin_id = admin.id if admin else None

    slug = "mastering-relational-databases-sql"
    course = db.query(Course).filter(Course.slug == slug).first()
    if not course:
        course = Course(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            title="Mastering Relational Databases & SQL",
            slug=slug,
            description=(
                "An in-depth, hands-on masterclass covering the relational model, database "
                "normalization, complex SQL joins, aggregations, correlated subqueries, "
                "transaction ACID guarantees, and query execution plans."
            ),
            subject="Database Systems",
            difficulty="intermediate",
            estimated_hours=6,
            is_published=True,
            source="seeded",
            is_private=False,
            created_by=admin_id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        logger.info("Created course: %s", course.title)
    else:
        logger.info("Course already exists: %s", course.title)

    # Clean existing lessons to keep seed idempotent
    db.query(Lesson).filter(Lesson.course_id == course.id).delete()

    lessons_data = [
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220001"),
            "title": "The Relational Model, Entities & Keys",
            "order_index": 1,
            "estimated_minutes": 25,
            "topic_tags": ["dbms.er_model"],
            "content_md": """# The Relational Model, Entities & Integrity Constraints

## 1. Introduction to the Relational Model
The relational model, formulated by E.F. Codd in 1970, represents all data in the form of mathematical relations, commonly visualised as **tables**. 
- A **relation** corresponds to a table.
- A **tuple** corresponds to a single record or row.
- An **attribute** corresponds to a named column with a strictly typed domain.

## 2. Candidate Keys, Primary Keys and Superkeys
Every row in a relation must be uniquely identifiable:
- **Superkey**: Any set of attributes that uniquely identifies a row.
- **Candidate Key**: A minimal superkey—no proper subset can uniquely identify the row.
- **Primary Key**: The specific candidate key chosen by the database architect as the principal identifier.
- **Foreign Key**: An attribute (or set of attributes) in one relation that references a candidate/primary key in another relation.

## 3. Referential Integrity Constraints
Referential integrity dictates that a foreign key value must always match an existing primary key value in the referenced table, or else be `NULL`.
When deleting or updating referenced rows, database engines support cascade actions:
```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    total_amount NUMERIC(10, 2) NOT NULL
);
```

> **Common Pitfall**: Students often assume foreign keys must have the same column name as the referenced primary key. In reality, column names can differ completely; only the underlying domains and data types must match.
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220002"),
            "title": "Database Normalization: 1NF, 2NF, 3NF & BCNF",
            "order_index": 2,
            "estimated_minutes": 35,
            "topic_tags": ["dbms.normalization"],
            "content_md": """# Database Normalization: 1NF, 2NF, 3NF and BCNF

## 1. Why Normalize?
Normalization systematically decomposes tables to eliminate redundancy and prevent data anomalies:
- **Insertion Anomaly**: Inability to record certain facts without adding unrelated dummy records.
- **Deletion Anomaly**: Unintentional loss of valuable information when deleting unrelated attributes.
- **Update Anomaly**: Modifying a fact in one place while leaving identical copies unupdated elsewhere.

## 2. Normal Forms Step-by-Step

### First Normal Form (1NF)
- Each cell contains atomic (indivisible) values.
- No repeating groups or arrays stored in a single field.
- Unique column names and order of rows does not matter.

### Second Normal Form (2NF)
- Must already satisfy 1NF.
- **No Partial Dependencies**: All non-key attributes must be fully functionally dependent on the *entire* primary key, not just a part of a composite key.
- If a table has a single-column primary key and is in 1NF, it is automatically in 2NF!

### Third Normal Form (3NF)
- Must already satisfy 2NF.
- **No Transitive Dependencies**: Non-key attributes must depend directly on the primary key, not via another non-key attribute ($A \\rightarrow B \\rightarrow C$).

### Boyce-Codd Normal Form (BCNF)
- A stricter version of 3NF. For every non-trivial functional dependency $X \\rightarrow Y$, $X$ must be a superkey.

```sql
-- Unnormalized Order Items:
-- (order_id, product_id, product_name, unit_price, quantity)
-- Normalized to 3NF:
-- products(product_id PK, product_name, unit_price)
-- order_items(order_id, product_id, quantity, PRIMARY KEY (order_id, product_id))
```
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220003"),
            "title": "SQL Joins Demystified: INNER, LEFT, RIGHT & FULL OUTER",
            "order_index": 3,
            "estimated_minutes": 30,
            "topic_tags": ["dbms.sql_joins"],
            "content_md": """# SQL Joins Demystified

## 1. How Joins Actually Work Under the Hood
A JOIN evaluates relationships between two tables by forming pairs of rows and testing a join predicate.

### Conceptual Execution Model:
1. Form the Cartesian product (all possible row combinations).
2. Apply the `ON` condition filter.
3. For outer joins, preserve unmatched rows from the designated side by padding missing columns with `NULL`.

## 2. Join Variations

### INNER JOIN
Returns only rows where the join predicate evaluates to `TRUE`.
```sql
SELECT u.full_name, e.enrolled_at
FROM users u
INNER JOIN enrollments e ON u.id = e.user_id;
```

### LEFT OUTER JOIN
Preserves **all** rows from the left table. If no matching row exists on the right, all right-table columns produce `NULL`.
```sql
SELECT u.full_name, e.course_id
FROM users u
LEFT JOIN enrollments e ON u.id = e.user_id;
```

### FULL OUTER JOIN
Retains all rows from both tables, populating `NULL` for missing sides.

> **CRITICAL MISCONCEPTION**:
> Many beginners think a JOIN combines all rows from both tables into one list (confusing it with `UNION`).
> Remember: `UNION` stacks rows vertically. A `JOIN` combines columns horizontally based on matching key values!
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220004"),
            "title": "Aggregations, GROUP BY and the HAVING Clause",
            "order_index": 4,
            "estimated_minutes": 25,
            "topic_tags": ["dbms.sql_joins"],
            "content_md": """# Aggregations, GROUP BY & HAVING

## 1. Aggregate Functions
SQL aggregate functions collapse sets of row values into a single scalar value:
- `COUNT(*)` counts all rows including NULLs.
- `COUNT(column)` counts non-NULL values in that column.
- `SUM(column)`, `AVG(column)`, `MIN(column)`, `MAX(column)`.

## 2. The Mechanics of GROUP BY
`GROUP BY` partitions table rows into buckets sharing identical values for specified columns.
```sql
SELECT c.difficulty, COUNT(*) AS course_count, AVG(c.estimated_hours) AS avg_hours
FROM courses c
GROUP BY c.difficulty;
```

## 3. WHERE vs HAVING: The Crucial Distinction
- **`WHERE`**: Filters raw input rows **before** groups are formed and aggregates calculated.
- **`HAVING`**: Filters groups **after** aggregation has occurred.

```sql
SELECT c.subject, COUNT(l.id) AS total_lessons
FROM courses c
JOIN lessons l ON c.id = l.course_id
WHERE c.is_published = true          -- Filters rows BEFORE grouping
GROUP BY c.subject
HAVING COUNT(l.id) >= 5;            -- Filters groups AFTER aggregation
```
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220005"),
            "title": "Subqueries, Correlated Subqueries & CTEs",
            "order_index": 5,
            "estimated_minutes": 30,
            "topic_tags": ["dbms.sql_joins"],
            "content_md": """# Subqueries, Correlated Subqueries & CTEs

## 1. Scalar & Multi-Row Subqueries
A subquery is a query nested within another query.
- **Scalar Subquery**: Returns a single row and single column. Can appear anywhere an expression is valid.
- **Multi-row Subquery**: Evaluated using set operators: `IN`, `NOT IN`, `ANY`, `ALL`.

## 2. Correlated Subqueries
A correlated subquery references columns from the outer query table, executing once for each candidate row evaluated by the outer query:
```sql
SELECT u.email, u.full_name
FROM users u
WHERE EXISTS (
    SELECT 1 FROM enrollments e
    WHERE e.user_id = u.id AND e.completed_at IS NOT NULL
);
```

## 3. Common Table Expressions (CTEs)
CTEs defined via `WITH` make complex nested logic readable and modular:
```sql
WITH ActiveLearners AS (
    SELECT user_id, COUNT(*) AS completed_count
    FROM enrollments
    WHERE completed_at IS NOT NULL
    GROUP BY user_id
)
SELECT u.email, al.completed_count
FROM users u
JOIN ActiveLearners al ON u.id = al.user_id
ORDER BY al.completed_count DESC;
```
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220006"),
            "title": "Transactions, ACID Guarantees & Isolation Levels",
            "order_index": 6,
            "estimated_minutes": 35,
            "topic_tags": ["dbms.transactions"],
            "content_md": """# Transactions, ACID Guarantees & Isolation

## 1. What is a Transaction?
A database transaction is an atomic unit of execution consisting of one or more database operations.

## 2. The ACID Properties
- **Atomicity**: All changes succeed, or all changes roll back ("All-or-Nothing").
- **Consistency**: The database transitions from one valid state satisfying all constraints to another.
- **Isolation**: Concurrent transactions execute without interfering with one another.
- **Durability**: Once committed, changes survive server crashes or power failures.

## 3. Concurrency Anomalies & SQL Isolation Levels
When multiple transactions execute simultaneously, unwanted phenomena can occur:
- **Dirty Read**: Reading uncommitted data modified by another transaction.
- **Non-Repeatable Read**: Re-reading a row finds modified data because another transaction committed an update.
- **Phantom Read**: Re-running a query finds newly inserted rows committed by another transaction.

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read |
| :--- | :---: | :---: | :---: |
| **Read Uncommitted** | Yes | Yes | Yes |
| **Read Committed** | No | Yes | Yes |
| **Repeatable Read** | No | No | Yes |
| **Serializable** | No | No | No |
""",
        },
        {
            "id": uuid.UUID("22222222-2222-2222-2222-222222220007"),
            "title": "Database Indexing, B-Trees & Query Optimization",
            "order_index": 7,
            "estimated_minutes": 30,
            "topic_tags": ["dbms.transactions"],
            "content_md": """# Database Indexing, B-Trees & Optimization

## 1. The Purpose of an Index
Without an index, the database engine must execute a **Sequential Scan** (Full Table Scan), inspecting every page on disk ($O(N)$). 
An index creates a specialized auxiliary data structure—most commonly a **B-Tree** ($O(\\log N)$)—mapping search keys directly to physical row pointers (`ctid` in Postgres, `RowID`).

## 2. Clustered vs Non-Clustered Indexes
- **Clustered Index**: Dictates the physical sorting order of rows on disk (PostgreSQL uses `CLUSTER`, InnoDB stores primary keys as the clustered index).
- **Non-Clustered Index**: Stores a sorted copy of the indexed keys along with pointers back to the base table.

## 3. Writing SARGable Queries
A query is **SARGable** (Search Argument Able) when the database optimizer can use an index:
```sql
-- NON-SARGABLE (disables standard index on created_at):
SELECT * FROM users WHERE EXTRACT(YEAR FROM created_at) = 2026;

-- SARGABLE (index scan on created_at):
SELECT * FROM users 
WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01';
```

## 4. Reading EXPLAIN Plans
Always inspect execution plans:
```sql
EXPLAIN ANALYZE
SELECT * FROM lessons WHERE course_id = '11111111-1111-1111-1111-111111111111';
```
Look for: `Index Scan using ix_lessons_course_id` vs `Seq Scan`.
""",
        },
    ]

    for item in lessons_data:
        lesson = Lesson(
            id=item["id"],
            course_id=course.id,
            title=item["title"],
            order_index=item["order_index"],
            estimated_minutes=item["estimated_minutes"],
            topic_tags=item["topic_tags"],
            content_md=item["content_md"].strip(),
            video_url=None,
        )
        db.add(lesson)

    # Seed enrollment for student if student was seeded
    if student:
        existing_enr = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == student.id, Enrollment.course_id == course.id)
            .first()
        )
        if not existing_enr:
            enr = Enrollment(
                user_id=student.id,
                course_id=course.id,
                enrolled_at=datetime.now(timezone.utc),
            )
            db.add(enr)
            logger.info("Enrolled student %s into course.", student.email)

    db.commit()
    logger.info("Successfully seeded course with %d lessons.", len(lessons_data))
    return course


def seed_badges(db: Session) -> None:
    """TODO(M4): ~15 badges with JSONB criteria (plan.md §9.4)."""
    logger.info("seed_badges placeholder (owned by Member 4).")


def seed_challenges(db: Session) -> None:
    """TODO(M4): daily challenge template pool (plan.md §9.5)."""
    logger.info("seed_challenges placeholder (owned by Member 4).")


def main() -> None:
    from app.database import Base, database_is_configured, get_engine, get_session_factory

    if not database_is_configured():
        logger.warning("DATABASE_URL is not configured. Seed cannot run against a database.")
        return

    # Ensure tables exist
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    db = get_session_factory()()
    try:
        seed_courses(db)
        try:
            seed_badges(db)
        except Exception:
            pass
        try:
            seed_challenges(db)
        except Exception:
            pass
        db.commit()
        logger.info("Database seeding completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
