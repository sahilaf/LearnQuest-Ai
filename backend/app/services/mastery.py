"""Topic mastery and misconception capture. OWNER: Member 1. See plan.md 6.5 and 6.10.

The mastery score tells you a learner is struggling. The misconception tells you WHY,
and that is what the tutor explains. Capturing it is Tier 1 (plan.md 0.1).
"""

LEARNING_RATE = 0.3
DECAY_AFTER_DAYS = 7
DECAY_FACTOR = 0.95
MASTERY_MIN = 0.05
MASTERY_MAX = 0.99


def update_mastery(db, user_id, topic_tag: str, correct: int, attempted: int) -> float:
    """Exponential moving average toward the observed correct rate.

        correct_rate = correct / attempted
        new = old + LEARNING_RATE * (correct_rate - old)
        if stale by more than DECAY_AFTER_DAYS: new *= DECAY_FACTOR
        clamp to [MASTERY_MIN, MASTERY_MAX]

    Describe this in the report as a simplified exponential-moving-average form of
    Bayesian Knowledge Tracing.
    """
    raise NotImplementedError("TODO(M1): week 3")


MAX_MISCONCEPTION_CHARS = 200
CLEAR_AFTER_CORRECT_STREAK = 2


async def capture_misconception(db, user_id, topic_tag: str, question, user_answer: str):
    """Ask the LLM what the learner believes that is untrue, and store it.

    Returns None when no specific belief can be identified - and storing None is the
    right outcome. An invented misconception tells the learner they think something
    they do not, which is worse than saying nothing (plan.md 6.10).
    """
    raise NotImplementedError("TODO(M1): week 2 - this is the Tier 1 deliverable")


# TODO(M1): register the quiz.submitted handler here in week 2.
# from app.services.events import on
#
# @on("quiz.submitted")
# def _on_quiz_submitted(db, user_id, payload):
#     ...
