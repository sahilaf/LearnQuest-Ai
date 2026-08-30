"""Personalized recommendations.

OWNER: Member 1. See plan.md 6.5.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
def list_recommendations(user: CurrentUser) -> dict:
    """Ranked recommendations. Every item carries a human-readable reason.

    The reason string is what sells this feature in the demo - never ship a
    recommendation without one (plan.md 6.5).
    """
    # TODO(M1): services.recommender.recommend(), cached 1h in the recommendations table.
    return {"items": []}


@router.post("/{recommendation_id}/dismiss")
def dismiss(recommendation_id: str, user: CurrentUser) -> dict:
    return {"id": recommendation_id, "dismissed": True}


@router.get("/daily-plan")
def daily_plan(user: CurrentUser) -> dict:
    """A time-boxed plan honouring preferences.daily_goal_minutes."""
    # TODO(M1): fill the budget with recommended lessons + revision + a quiz.
    return {"minutes": 0, "items": []}
