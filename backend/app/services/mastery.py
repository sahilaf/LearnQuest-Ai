"""Topic mastery model. OWNER: Member 1. See plan.md 6.5."""

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


# TODO(M1): register the quiz.submitted handler here in week 3.
# from app.services.events import on
#
# @on("quiz.submitted")
# def _on_quiz_submitted(db, user_id, payload):
#     ...
