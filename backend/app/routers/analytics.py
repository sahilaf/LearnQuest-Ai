"""Learner and admin analytics.

OWNER: Member 4. See plan.md 9.7.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import AdminUser, CurrentUser

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/me/summary")
def my_summary(user: CurrentUser) -> dict:
    """Headline numbers for the stats page."""
    # TODO(M4): lessons completed, quizzes taken, average score, total minutes.
    return {"lessons_completed": 0, "quizzes_taken": 0, "avg_score": 0, "minutes": 0}


@router.get("/me/activity")
def my_activity(user: CurrentUser, days: int = 56) -> dict:
    """Minutes per day for the activity chart. Default 8 weeks."""
    # TODO(M4): group lesson_progress.seconds_spent by day.
    return {"days": days, "items": []}


@router.get("/mastery/me")
def my_mastery(user: CurrentUser) -> dict:
    """Topic mastery for M4's radar chart.

    OWNER NOTE: this endpoint is implemented by Member 1 (it reads topic_mastery)
    but consumed by Member 4. See plan.md 6.5.
    """
    # TODO(M1): read topic_mastery for this user.
    return {"items": []}


@router.get("/admin/overview")
def admin_overview(admin: AdminUser) -> dict:
    """DAU/WAU, signups, course popularity, quiz difficulty, tutor usage."""
    # TODO(M4): the quiz-difficulty breakdown (lowest correct-rate questions) is
    # the strongest talking point here - build it properly.
    return {
        "dau": 0, "wau": 0, "new_signups": 0,
        "course_popularity": [], "hardest_questions": [], "tutor_messages": 0,
    }
