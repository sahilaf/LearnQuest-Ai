"""Seed SQL practice problems. Idempotent - upserts by slug.

Each problem has a reference solution and several test cases with their own seed
data. Expected output is never hand-written: grading runs the reference against
the same seed and compares. `validate()` runs every reference against every case
so a broken problem fails here, loudly, rather than failing a student.

Hidden cases are the edge cases a naive answer misses - the customer with no
orders, the employee with no manager, a tie. They are what make this a judge
rather than a spell-checker.

Tags come from the topics vocabulary only.

    python -m app.seed.practice_problems
"""

from __future__ import annotations

import logging

logger = logging.getLogger("learnquest.seed.practice")

PROBLEMS = [
    {
        "slug": "customer-spend-summary",
        "title": "Customer spend summary",
        "topic_tag": "dbms.sql_joins",
        "difficulty": "easy",
        "order_matters": True,
        "statement_md": (
            "Return every customer's `customer_id`, `name` and the total they have spent "
            "on **completed** orders as `total_spent`.\n\n"
            "A customer with no completed orders must still appear, with `total_spent` "
            "of `0`.\n\n"
            "Sort by `total_spent` descending, then `customer_id` ascending."
        ),
        "input_format": (
            "- `customers(customer_id INT, name TEXT)`\n"
            "- `orders(order_id INT, customer_id INT, amount REAL, status TEXT)`"
        ),
        "output_format": "Columns: `customer_id`, `name`, `total_spent`",
        "constraints": [
            "`status` is one of `completed`, `cancelled`, `pending`",
            "Amounts are non-negative",
        ],
        "starter_code": "SELECT\n  c.customer_id,\n  c.name\n  -- total_spent\nFROM customers c\n",
        "reference_sql": (
            "SELECT c.customer_id, c.name, "
            "COALESCE(SUM(CASE WHEN o.status = 'completed' THEN o.amount END), 0) AS total_spent "
            "FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id "
            "GROUP BY c.customer_id, c.name "
            "ORDER BY total_spent DESC, c.customer_id ASC"
        ),
        "cases": [
            (
                "Two customers with orders",
                False,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT, amount REAL, status TEXT);
INSERT INTO customers VALUES (1,'Alice'),(2,'Bob');
INSERT INTO orders VALUES (101,1,50,'completed'),(102,1,30,'completed'),(103,2,20,'completed');""",
            ),
            (
                "A customer with no orders at all",
                True,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT, amount REAL, status TEXT);
INSERT INTO customers VALUES (1,'Alice'),(2,'Bob'),(3,'Chen');
INSERT INTO orders VALUES (101,1,50,'completed'),(103,2,20,'completed');""",
            ),
            (
                "Cancelled orders must not count",
                True,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT, amount REAL, status TEXT);
INSERT INTO customers VALUES (1,'Alice'),(2,'Bob');
INSERT INTO orders VALUES (101,1,500,'cancelled'),(102,1,10,'completed'),(103,2,40,'pending');""",
            ),
        ],
    },
    {
        "slug": "orphaned-orders",
        "title": "Orders pointing at nobody",
        "topic_tag": "dbms.er_model",
        "difficulty": "easy",
        "order_matters": True,
        "statement_md": (
            "Some `orders` reference a `customer_id` that does not exist in `customers` - "
            "exactly what a foreign key would have prevented.\n\n"
            "Return the `order_id` of every such orphaned order, ascending."
        ),
        "input_format": (
            "- `customers(customer_id INT, name TEXT)`\n"
            "- `orders(order_id INT, customer_id INT)`"
        ),
        "output_format": "Column: `order_id`",
        "constraints": ["There is no foreign key constraint on `orders.customer_id`"],
        "starter_code": "SELECT o.order_id\nFROM orders o\n",
        "reference_sql": (
            "SELECT o.order_id FROM orders o "
            "LEFT JOIN customers c ON c.customer_id = o.customer_id "
            "WHERE c.customer_id IS NULL ORDER BY o.order_id"
        ),
        "cases": [
            (
                "One orphan",
                False,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT);
INSERT INTO customers VALUES (1,'Alice'),(2,'Bob');
INSERT INTO orders VALUES (10,1),(11,2),(12,9);""",
            ),
            (
                "No orphans at all",
                True,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT);
INSERT INTO customers VALUES (1,'Alice');
INSERT INTO orders VALUES (10,1),(11,1);""",
            ),
            (
                "A NULL customer_id is also an orphan",
                True,
                """CREATE TABLE customers(customer_id INT, name TEXT);
CREATE TABLE orders(order_id INT, customer_id INT);
INSERT INTO customers VALUES (1,'Alice');
INSERT INTO orders VALUES (10,1),(11,NULL),(12,7);""",
            ),
        ],
    },
    {
        "slug": "employees-and-managers",
        "title": "Employees and their managers",
        "topic_tag": "dbms.sql_joins",
        "difficulty": "medium",
        "order_matters": True,
        "statement_md": (
            "Each employee may report to a manager, who is also in `employees`.\n\n"
            "Return every employee's `name` and their manager's name as `manager`. "
            "Someone with no manager must still appear, with `manager` as `NULL`.\n\n"
            "Sort by employee `name`."
        ),
        "input_format": "- `employees(emp_id INT, name TEXT, manager_id INT)`",
        "output_format": "Columns: `name`, `manager`",
        "constraints": ["`manager_id` is NULL for the top of the hierarchy"],
        "starter_code": "SELECT e.name\nFROM employees e\n",
        "reference_sql": (
            "SELECT e.name, m.name AS manager FROM employees e "
            "LEFT JOIN employees m ON m.emp_id = e.manager_id ORDER BY e.name"
        ),
        "cases": [
            (
                "A small team",
                False,
                """CREATE TABLE employees(emp_id INT, name TEXT, manager_id INT);
INSERT INTO employees VALUES (1,'Dana',NULL),(2,'Eli',1),(3,'Fay',1);""",
            ),
            (
                "Three levels deep",
                True,
                """CREATE TABLE employees(emp_id INT, name TEXT, manager_id INT);
INSERT INTO employees VALUES (1,'Ada',NULL),(2,'Ben',1),(3,'Cy',2),(4,'Di',2);""",
            ),
        ],
    },
    {
        "slug": "duplicate-emails",
        "title": "Emails used more than once",
        "topic_tag": "dbms.er_model",
        "difficulty": "easy",
        "order_matters": True,
        "statement_md": (
            "`users.email` should have been a unique key, but it was not enforced.\n\n"
            "Return each `email` that appears more than once, with how many times as "
            "`uses`, sorted by `email`."
        ),
        "input_format": "- `users(user_id INT, email TEXT)`",
        "output_format": "Columns: `email`, `uses`",
        "constraints": ["Emails are already lowercase"],
        "starter_code": "SELECT email\nFROM users\n",
        "reference_sql": (
            "SELECT email, COUNT(*) AS uses FROM users "
            "GROUP BY email HAVING COUNT(*) > 1 ORDER BY email"
        ),
        "cases": [
            (
                "One duplicate",
                False,
                """CREATE TABLE users(user_id INT, email TEXT);
INSERT INTO users VALUES (1,'a@x.io'),(2,'b@x.io'),(3,'a@x.io');""",
            ),
            (
                "Everyone unique",
                True,
                """CREATE TABLE users(user_id INT, email TEXT);
INSERT INTO users VALUES (1,'a@x.io'),(2,'b@x.io');""",
            ),
            (
                "Used three times",
                True,
                """CREATE TABLE users(user_id INT, email TEXT);
INSERT INTO users VALUES (1,'z@x.io'),(2,'z@x.io'),(3,'z@x.io'),(4,'m@x.io'),(5,'m@x.io');""",
            ),
        ],
    },
    {
        "slug": "students-in-no-course",
        "title": "Students not enrolled anywhere",
        "topic_tag": "dbms.sql_joins",
        "difficulty": "medium",
        "order_matters": True,
        "statement_md": (
            "Return the `name` of every student who is enrolled in **no** course, "
            "sorted by `name`."
        ),
        "input_format": (
            "- `students(student_id INT, name TEXT)`\n"
            "- `enrollments(student_id INT, course_id INT)`"
        ),
        "output_format": "Column: `name`",
        "constraints": ["A student may be enrolled in several courses"],
        "starter_code": "SELECT s.name\nFROM students s\n",
        "reference_sql": (
            "SELECT s.name FROM students s "
            "WHERE NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.student_id = s.student_id) "
            "ORDER BY s.name"
        ),
        "cases": [
            (
                "One student left out",
                False,
                """CREATE TABLE students(student_id INT, name TEXT);
CREATE TABLE enrollments(student_id INT, course_id INT);
INSERT INTO students VALUES (1,'Ali'),(2,'Bea'),(3,'Cai');
INSERT INTO enrollments VALUES (1,10),(2,10);""",
            ),
            (
                "Enrolled in several courses is still enrolled",
                True,
                """CREATE TABLE students(student_id INT, name TEXT);
CREATE TABLE enrollments(student_id INT, course_id INT);
INSERT INTO students VALUES (1,'Ali'),(2,'Bea');
INSERT INTO enrollments VALUES (1,10),(1,11),(1,12);""",
            ),
        ],
    },
    {
        "slug": "top-product-per-category",
        "title": "Best-selling product in each category",
        "topic_tag": "dbms.sql_joins",
        "difficulty": "hard",
        "order_matters": True,
        "statement_md": (
            "For each `category`, return the product with the highest total quantity "
            "sold as `product`, with that total as `units`.\n\n"
            "If two products tie, return the one with the **smaller** `product_id`.\n\n"
            "Sort by `category`."
        ),
        "input_format": (
            "- `products(product_id INT, name TEXT, category TEXT)`\n"
            "- `sales(sale_id INT, product_id INT, qty INT)`"
        ),
        "output_format": "Columns: `category`, `product`, `units`",
        "constraints": ["Every category has at least one product with a sale"],
        "starter_code": "SELECT p.category\nFROM products p\n",
        "reference_sql": (
            "WITH totals AS ("
            "  SELECT p.category, p.product_id, p.name, SUM(s.qty) AS units "
            "  FROM products p JOIN sales s ON s.product_id = p.product_id "
            "  GROUP BY p.category, p.product_id, p.name"
            "), ranked AS ("
            "  SELECT t.*, (SELECT COUNT(*) FROM totals t2 WHERE t2.category = t.category "
            "    AND (t2.units > t.units OR (t2.units = t.units AND t2.product_id < t.product_id))) AS rnk "
            "  FROM totals t"
            ") SELECT category, name AS product, units FROM ranked WHERE rnk = 0 ORDER BY category"
        ),
        "cases": [
            (
                "Two categories",
                False,
                """CREATE TABLE products(product_id INT, name TEXT, category TEXT);
CREATE TABLE sales(sale_id INT, product_id INT, qty INT);
INSERT INTO products VALUES (1,'Pen','office'),(2,'Ink','office'),(3,'Mug','kitchen');
INSERT INTO sales VALUES (1,1,5),(2,2,9),(3,3,4);""",
            ),
            (
                "A tie goes to the smaller product_id",
                True,
                """CREATE TABLE products(product_id INT, name TEXT, category TEXT);
CREATE TABLE sales(sale_id INT, product_id INT, qty INT);
INSERT INTO products VALUES (7,'Bolt','tools'),(3,'Nut','tools');
INSERT INTO sales VALUES (1,7,6),(2,3,6);""",
            ),
            (
                "Totals span several sales",
                True,
                """CREATE TABLE products(product_id INT, name TEXT, category TEXT);
CREATE TABLE sales(sale_id INT, product_id INT, qty INT);
INSERT INTO products VALUES (1,'Tea','food'),(2,'Rice','food');
INSERT INTO sales VALUES (1,1,3),(2,1,3),(3,1,3),(4,2,8);""",
            ),
        ],
    },
]


def validate() -> list[str]:
    """Run every reference against every case. Returns problems, empty if all good."""
    from app.services.sql_runner import _run

    errors = []
    for problem in PROBLEMS:
        for title, _hidden, setup in problem["cases"]:
            try:
                _run(setup, problem["reference_sql"], authorize=False)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{problem['slug']} / {title}: {exc}")
    return errors


def examples_for(problem: dict) -> list[dict]:
    """Worked examples built from the visible cases, by running the reference.

    Generated, never typed, so an example cannot disagree with the grader.
    """
    from app.services.sql_runner import _run, format_rows

    out = []
    for title, hidden, setup in problem["cases"]:
        if hidden:
            continue
        rows = _run(setup, problem["reference_sql"], authorize=False)
        inserts = [line.strip() for line in setup.splitlines() if line.strip().upper().startswith("INSERT")]
        out.append(
            {
                "title": title,
                "input": "\n".join(inserts),
                "output": format_rows(rows),
                "explanation": None,
            }
        )
    return out


def seed(db) -> int:
    from app.models.practice import PracticeProblem, PracticeTestCase

    errors = validate()
    if errors:
        raise RuntimeError("Refusing to seed broken practice problems:\n" + "\n".join(errors))

    written = 0
    for position, spec in enumerate(PROBLEMS):
        problem = db.query(PracticeProblem).filter(PracticeProblem.slug == spec["slug"]).first()
        if problem is None:
            problem = PracticeProblem(slug=spec["slug"])
            db.add(problem)

        problem.title = spec["title"]
        problem.topic_tag = spec["topic_tag"]
        problem.difficulty = spec["difficulty"]
        problem.statement_md = spec["statement_md"]
        problem.input_format = spec["input_format"]
        problem.output_format = spec["output_format"]
        problem.constraints = spec["constraints"]
        problem.examples = examples_for(spec)
        problem.starter_code = spec["starter_code"]
        problem.reference_sql = spec["reference_sql"]
        problem.order_matters = spec["order_matters"]
        problem.position = position
        db.flush()

        # Rebuild cases so edits to the seed are picked up on re-run.
        db.query(PracticeTestCase).filter(PracticeTestCase.problem_id == problem.id).delete()
        for index, (title, hidden, setup) in enumerate(spec["cases"]):
            db.add(
                PracticeTestCase(
                    problem_id=problem.id,
                    title=title,
                    is_hidden=hidden,
                    setup_sql=setup,
                    position=index,
                )
            )
        written += 1

    db.commit()
    return written


if __name__ == "__main__":
    from app.database import get_session_factory

    session = get_session_factory()()
    try:
        print(f"Seeded {seed(session)} practice problems.")
    finally:
        session.close()
