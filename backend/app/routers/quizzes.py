"""Quiz attempts (M2) and AI generation (M1).

OWNER: Member 2 + Member 1. See plan.md 7.3 and 6.4.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


# ---------------- Member 2: taking quizzes ----------------

@router.get("/{quiz_id}")
def get_quiz(quiz_id: str, user: CurrentUser) -> dict:
    """Questions WITHOUT correct_answer or explanation.

    SECURITY: stripping these is not optional - see plan.md 7.3.
    """
    # TODO(M2): serialise with a schema that has no correct_answer field at all.
    return {"id": quiz_id, "title": None, "questions": []}


@router.post("/{quiz_id}/attempts")
def start_attempt(quiz_id: str, user: CurrentUser) -> dict:
    # TODO(M2): create a quiz_attempts row with started_at.
    return {"attempt_id": None, "quiz_id": quiz_id}


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, user: CurrentUser, payload: dict) -> dict:
    """Grade server-side, write attempt_answers, then emit("quiz.submitted", ...).

    Copy topic_tag from each question onto attempt_answers - M1 aggregates on it.
    """
    # TODO(M2): grade, persist, emit.
    return {"attempt_id": attempt_id, "score": 0, "correct": 0, "total": 0}


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: str, user: CurrentUser) -> dict:
    """Result screen: score plus per-question explanations."""
    # TODO(M2): explanations ARE allowed here - the attempt is already submitted.
    return {"attempt_id": attempt_id, "answers": []}


# ---------------- Member 1: AI generation ----------------

@router.post("/generate")
async def generate_quiz(user: CurrentUser, payload: dict) -> dict:
    """Generate a quiz from a lesson. Returns M2's exact quiz shape.

    Body: {lesson_id, num_questions=5, difficulty="auto", types=["mcq","true_false"]}
    """
    # TODO(M1): call services.quiz_generator.generate_quiz, then emit("quiz.generated", ...).
    return {"id": None, "title": None, "questions": [], "source": "ai_generated"}


@router.post("/generate/adaptive")
async def generate_adaptive_quiz(user: CurrentUser, payload: dict) -> dict:
    """Weak-topic mix drawn from topic_mastery, ignoring lesson scope."""
    # TODO(M1): pick the lowest-mastery topics, then generate.
    return {"id": None, "questions": [], "source": "ai_generated"}


@router.post("/attempts/{attempt_id}/grade-open")
async def grade_open_answer(attempt_id: str, user: CurrentUser, payload: dict) -> dict:
    """LLM grading for short_answer questions only."""
    # TODO(M1): return {is_correct, score_0_1, feedback}.
    return {"is_correct": False, "score_0_1": 0.0, "feedback": ""}
