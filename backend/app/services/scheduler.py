"""Review queue scheduling. OWNER: Member 1. See plan.md 3.3 and 6.12.

The queue is what the app opens to. It schedules TOPICS, not stored questions - the
question is generated fresh each time, so a learner cannot memorise the item instead
of the idea.
"""

MAX_DAILY_ITEMS = 15
EASE = 2.5
MAX_INTERVAL_DAYS = 60
WRONG_INTERVAL_DAYS = 2


def next_interval(interval_days: int, correct: bool) -> int:
    """SM-2-lite. Defensible in a viva, and about ten lines of code.

        correct -> interval * 2.5, capped at 60 days
        wrong   -> back to 2 days
    """
    if not correct:
        return WRONG_INTERVAL_DAYS
    return min(int(interval_days * EASE), MAX_INTERVAL_DAYS)


def due_items(db, user_id, limit: int = MAX_DAILY_ITEMS):
    """Topics due today, interleaved rather than blocked by topic.

    Interleaving is a real learning gain for almost no extra code: sort the due set so
    the same topic never appears twice in a row.
    """
    raise NotImplementedError("TODO(M1): week 3")


def record_answer(db, user_id, item_id, correct: bool):
    """Update the item's interval, streak and due_at after an answer."""
    raise NotImplementedError("TODO(M1): week 3")


def enrol_topic(db, user_id, topic_tag: str, source_lesson_id=None):
    """Add a topic to the queue the first time the learner touches it."""
    raise NotImplementedError("TODO(M1): week 3")
