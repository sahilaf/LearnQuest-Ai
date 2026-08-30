"""Personalized recommendations. OWNER: Member 1. See plan.md 6.5."""

WEIGHTS = {
    "weakness": 0.45,      # 1 - mastery of the lesson's topics
    "prerequisite": 0.25,  # next unstarted lesson in an enrolled course
    "recency": 0.20,       # topic not practiced in N days
    "popularity": 0.10,    # completion rate across all users
}

CACHE_TTL_SECONDS = 3600


def recommend(db, user_id, limit: int = 5) -> list[dict]:
    """Return ranked recommendations, each with a human-readable `reason`.

    Example reason: "You scored 40% on loops last week."
    Never return an item without one - the reason is what sells this in the demo.
    """
    raise NotImplementedError("TODO(M1): week 3")


def daily_plan(db, user_id, minutes: int = 30) -> dict:
    """Fill a time budget with recommended lessons, revision and one quiz."""
    raise NotImplementedError("TODO(M1): week 3")
