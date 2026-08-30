"""XP, levels, streaks and badges. OWNER: Member 4. See plan.md 9.2-9.4."""

XP_AWARDS = {
    "lesson.completed": 50,
    "quiz.submitted_base": 10,
    "quiz.per_correct": 5,
    "quiz.perfect_bonus": 25,
    "course.completed": 200,
    "tutor.session": 5,
    "daily.login": 10,
}

TUTOR_XP_DAILY_CAP = 25
STREAK_BONUS_PER_DAY = 5
STREAK_BONUS_MAX_DAYS = 10


def xp_for_level(n: int) -> int:
    """Level curve: L2 at 283 XP, L5 at 1118, L10 at 3162."""
    return int(100 * (n**1.5))


def level_for_xp(xp: int) -> int:
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def award_xp(db, user_id, event_type: str, amount: int, ref_type=None, ref_id=None) -> None:
    """Write an xp_events row AND update user_stats. Never do one without the other."""
    raise NotImplementedError("TODO(M4): week 1")


def update_streak(db, user_id, local_date) -> int:
    """Same day -> no change. Yesterday -> increment. Otherwise -> reset to 1.

    Use the USER'S local date, not server UTC. Server UTC silently breaks streaks
    for anyone east of London and only shows up during the demo (plan.md 9.3).
    """
    raise NotImplementedError("TODO(M4): week 2")


# TODO(M4): register handlers here in week 1.
# from app.services.events import on
#
# @on("lesson.completed")
# def _on_lesson_completed(db, user_id, payload):
#     ...
