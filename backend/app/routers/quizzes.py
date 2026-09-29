import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import database_is_configured, get_db
from app.database import release_connection
from app.deps import CurrentUser
from app.models.quiz import AttemptAnswer, Question, Quiz, QuizAttempt
from app.schemas.quiz import (
    AttemptResultResponse,
    AttemptStartResponse,
    AttemptSubmitRequest,
    QuizPublicResponse,
)
from app.services.events import emit

logger = logging.getLogger("learnquest.quizzes")

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


# ---------------- Member 2: taking quizzes ----------------


@router.get("/lesson/{lesson_id}", response_model=QuizPublicResponse)
def get_quiz_by_lesson(
    lesson_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the quiz associated with a specific lesson.

    SECURITY (plan.md §7.3): questions returned MUST NOT include correct_answer or explanation.
    """
    if not db or not database_is_configured():
        return {
            "id": str(uuid.uuid4()),
            "lesson_id": lesson_id,
            "title": "Practice Quiz",
            "source": "manual",
            "difficulty": "beginner",
            "topic_tags": [],
            "questions": [],
        }

    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid lesson ID.",
            headers={"X-Error-Code": "INVALID_LESSON_ID"},
        ) from err

    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.lesson_id == l_uuid)
        .order_by(Quiz.created_at.desc())
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quiz found for lesson '{lesson_id}'.",
            headers={"X-Error-Code": "QUIZ_NOT_FOUND"},
        )

    return quiz.to_dict(include_questions=True, strip_answers=True)


@router.get("/{quiz_id}", response_model=QuizPublicResponse)
def get_quiz(
    quiz_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Questions WITHOUT correct_answer or explanation.

    SECURITY: stripping these is not optional - see plan.md 7.3.
    """
    if not db or not database_is_configured():
        return {
            "id": quiz_id,
            "title": "Practice Quiz",
            "source": "manual",
            "difficulty": "beginner",
            "topic_tags": [],
            "questions": [],
        }

    try:
        q_uuid = uuid.UUID(quiz_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz ID.",
            headers={"X-Error-Code": "INVALID_QUIZ_ID"},
        ) from err

    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.id == q_uuid)
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz '{quiz_id}' not found.",
            headers={"X-Error-Code": "QUIZ_NOT_FOUND"},
        )

    return quiz.to_dict(include_questions=True, strip_answers=True)


@router.post("/{quiz_id}/attempts", response_model=AttemptStartResponse)
def start_attempt(
    quiz_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Create a quiz_attempts row with started_at."""
    if not db or not database_is_configured():
        return {"attempt_id": str(uuid.uuid4()), "quiz_id": quiz_id}

    try:
        q_uuid = uuid.UUID(quiz_id)
        user_uuid = uuid.UUID(user["id"])
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid quiz or user ID.",
            headers={"X-Error-Code": "INVALID_ID"},
        ) from err

    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.id == q_uuid)
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz '{quiz_id}' not found.",
            headers={"X-Error-Code": "QUIZ_NOT_FOUND"},
        )

    if not quiz.questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start attempt: this quiz has no questions.",
            headers={"X-Error-Code": "EMPTY_QUIZ"},
        )

    attempt = QuizAttempt(
        user_id=user_uuid,
        quiz_id=q_uuid,
        score=0.0,
        total_questions=len(quiz.questions),
        correct_count=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {"attempt_id": str(attempt.id), "quiz_id": str(quiz.id)}


def _grade_short_answer_fallback(user_answer: str, correct_answer: str) -> bool:
    """Lenient fallback grading for short_answer when M1 LLM grading is offline.

    Checks if key terms from the expected answer appear in the learner's response.
    """
    clean_user = user_answer.strip().lower()
    clean_correct = correct_answer.strip().lower()
    if clean_user == clean_correct:
        return True
    # If the user answer contains the full expected answer or vice versa
    if clean_correct in clean_user or (len(clean_user) > 3 and clean_user in clean_correct):
        return True
    # Word-level intersection for multi-word answers
    correct_words = set(clean_correct.replace(",", " ").replace(".", " ").split())
    user_words = set(clean_user.replace(",", " ").replace(".", " ").split())
    if correct_words and len(correct_words & user_words) / len(correct_words) >= 0.6:
        return True
    return False


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: str,
    user: CurrentUser,
    payload: AttemptSubmitRequest | dict[str, Any],
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Grade server-side, write attempt_answers, then emit("quiz.submitted", ...).

    Copy topic_tag from each question onto attempt_answers - M1 aggregates on it.
    """
    if not db or not database_is_configured():
        return {
            "attempt_id": attempt_id,
            "quiz_id": str(uuid.uuid4()),
            "score": 100.0,
            "correct": 1,
            "total": 1,
            "duration_seconds": 10,
        }

    try:
        att_uuid = uuid.UUID(attempt_id)
        user_uuid = uuid.UUID(user["id"])
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid attempt or user ID.",
            headers={"X-Error-Code": "INVALID_ID"},
        ) from err

    attempt = (
        db.query(QuizAttempt)
        .options(
            joinedload(QuizAttempt.quiz).joinedload(Quiz.questions),
        )
        .filter(QuizAttempt.id == att_uuid)
        .first()
    )

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attempt '{attempt_id}' not found.",
            headers={"X-Error-Code": "ATTEMPT_NOT_FOUND"},
        )

    if attempt.user_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to submit this attempt.",
            headers={"X-Error-Code": "FORBIDDEN"},
        )

    if attempt.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This quiz attempt has already been submitted.",
            headers={"X-Error-Code": "ATTEMPT_ALREADY_SUBMITTED"},
        )

    quiz = attempt.quiz
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated quiz not found.",
            headers={"X-Error-Code": "QUIZ_NOT_FOUND"},
        )

    # Extract submitted answers dictionary
    answers_data = (
        payload.answers
        if isinstance(payload, AttemptSubmitRequest)
        else payload.get("answers", [])
    )
    user_answers_map: dict[str, str] = {}
    for item in answers_data:
        if isinstance(item, dict):
            qid = str(item.get("question_id", ""))
            ans = str(item.get("user_answer", "")).strip()
        else:
            qid = str(getattr(item, "question_id", ""))
            ans = str(getattr(item, "user_answer", "")).strip()
        if qid:
            user_answers_map[qid] = ans

    correct_count = 0
    total_questions = len(quiz.questions)

    # Grade each question and create AttemptAnswer rows
    for question in quiz.questions:
        q_id_str = str(question.id)
        user_ans = user_answers_map.get(q_id_str, "")
        is_correct = False

        if question.type in ("mcq", "true_false", "fill_blank"):
            is_correct = (
                user_ans.strip().lower() == question.correct_answer.strip().lower()
            )
        elif question.type == "short_answer":
            # Consume M1 open-response grading boundary if available, otherwise graceful fallback
            is_correct = _grade_short_answer_fallback(user_ans, question.correct_answer)
        else:
            # Default comparison
            is_correct = (
                user_ans.strip().lower() == question.correct_answer.strip().lower()
            )

        if is_correct:
            correct_count += 1

        # Denormalize question.topic_tag onto attempt_answers per plan.md §3.1
        attempt_answer = AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            user_answer=user_ans,
            is_correct=is_correct,
            topic_tag=question.topic_tag,
        )
        db.add(attempt_answer)

    now = datetime.now(timezone.utc)
    score_pct = (
        round((correct_count / total_questions) * 100.0, 2)
        if total_questions > 0
        else 0.0
    )
    started_at = attempt.started_at
    if started_at is not None and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    duration = (
        max(0, int((now - started_at).total_seconds()))
        if started_at is not None
        else 0
    )

    attempt.score = score_pct
    attempt.total_questions = total_questions
    attempt.correct_count = correct_count
    attempt.submitted_at = now
    attempt.duration_seconds = duration

    db.commit()
    db.refresh(attempt)

    # Emit standard cross-module event (M1 mastery + M4 gamification listen to this)
    try:
        emit(
            db=db,
            user_id=user_uuid,
            event_type="quiz.submitted",
            payload={
                "quiz_id": str(quiz.id),
                "attempt_id": str(attempt.id),
                "score": float(attempt.score),
                "correct": attempt.correct_count,
                "total": attempt.total_questions,
            },
        )
    except Exception as exc:
        logger.warning("Error emitting 'quiz.submitted' event: %s", exc)

    return {
        "attempt_id": str(attempt.id),
        "quiz_id": str(quiz.id),
        "score": float(attempt.score),
        "correct": attempt.correct_count,
        "total": attempt.total_questions,
        "duration_seconds": attempt.duration_seconds,
    }


@router.get("/attempts/{attempt_id}")
def get_attempt(
    attempt_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Result screen: score plus per-question explanations.

    SECURITY (plan.md 7.3): explanations ARE allowed here because the attempt has been submitted.
    """
    if not db or not database_is_configured():
        return {
            "attempt_id": attempt_id,
            "quiz_id": str(uuid.uuid4()),
            "score": 100.0,
            "total_questions": 1,
            "correct_count": 1,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 12,
            "answers": [],
        }

    try:
        att_uuid = uuid.UUID(attempt_id)
        user_uuid = uuid.UUID(user["id"])
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid attempt ID.",
            headers={"X-Error-Code": "INVALID_ATTEMPT_ID"},
        ) from err

    attempt = (
        db.query(QuizAttempt)
        .options(
            joinedload(QuizAttempt.answers).joinedload(AttemptAnswer.question),
            joinedload(QuizAttempt.quiz),
        )
        .filter(QuizAttempt.id == att_uuid)
        .first()
    )

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attempt '{attempt_id}' not found.",
            headers={"X-Error-Code": "ATTEMPT_NOT_FOUND"},
        )

    if attempt.user_id != user_uuid and user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this attempt.",
            headers={"X-Error-Code": "FORBIDDEN"},
        )

    answers_list: list[dict[str, Any]] = []
    # Sort answers by question order_index
    sorted_answers = sorted(
        attempt.answers,
        key=lambda a: a.question.order_index if a.question else 0,
    )

    for ans in sorted_answers:
        q = ans.question
        answers_list.append({
            "question_id": str(ans.question_id),
            "prompt": q.prompt if q else "",
            "type": q.type if q else "mcq",
            "options": q.options if q else None,
            "user_answer": ans.user_answer,
            "is_correct": ans.is_correct,
            "correct_answer": q.correct_answer if q else "",
            "explanation": q.explanation if q else None,
            "topic_tag": ans.topic_tag or (q.topic_tag if q else None),
        })

    return {
        "attempt_id": str(attempt.id),
        "quiz_id": str(attempt.quiz_id),
        "quiz_title": attempt.quiz.title if attempt.quiz else None,
        "score": float(attempt.score) if attempt.score is not None else 0.0,
        "total_questions": attempt.total_questions,
        "correct_count": attempt.correct_count,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "duration_seconds": attempt.duration_seconds,
        "answers": answers_list,
    }


# ---------------- Member 1: AI generation ----------------

def _generation_user(user: CurrentUser) -> uuid.UUID:
    try:
        return uuid.UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user."
        ) from err


def _spend_generation(db: Session, user_uuid: uuid.UUID, kind: str, params: dict) -> None:
    """Count this generation against the caller's daily allowance.

    The free tier is a per-day, per-model request quota shared with the tutor,
    misconception capture and Teach-Back, so one enthusiastic student can spend
    the whole app's budget. The job row is also the audit trail for what was
    generated and why.
    """
    from app.services.jobs import JobLimitReached, create_job

    try:
        create_job(db, user_uuid, kind, params)
    except JobLimitReached as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err)
        ) from err


@router.post("/generate")
async def generate_quiz(
    user: CurrentUser,
    payload: dict,
    db: Session | None = Depends(get_db),
) -> dict:
    """Generate a quiz from a lesson, written for this student.

    Body: {lesson_id, num_questions=5, difficulty="auto", types=["mcq","true_false"]}

    Difficulty defaults to the caller's mastery of the lesson's topic, and if
    they are carrying a live misconception about it the questions are aimed at
    that belief rather than sampling the topic at random. Returns M2's quiz
    shape with answers stripped, so it can be taken immediately.

    Synchronous: measured at roughly 8s for one call, inside the client's 30s
    budget. Course generation is the slow one and goes through /api/jobs.
    """
    from app.services.quiz_generator import generate_quiz as _generate

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    user_uuid = _generation_user(user)
    lesson_id = (payload or {}).get("lesson_id")
    if not lesson_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="lesson_id is required."
        )
    try:
        lesson_uuid = uuid.UUID(str(lesson_id))
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lesson_id."
        ) from err

    _spend_generation(db, user_uuid, "quiz", {"lesson_id": str(lesson_uuid)})

    try:
        return await _generate(
            db,
            lesson_id=lesson_uuid,
            user_id=user_uuid,
            num_questions=(payload or {}).get("num_questions", 5),
            difficulty=(payload or {}).get("difficulty", "auto"),
            types=tuple((payload or {}).get("types") or ("mcq", "true_false")),
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(err)
        ) from err
    except RuntimeError as err:
        # The model returned nothing usable. That is a service problem, not the
        # student's, and retrying often works.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)
        ) from err


@router.post("/generate/adaptive")
async def generate_adaptive_quiz(
    user: CurrentUser,
    payload: dict | None = None,
    db: Session | None = Depends(get_db),
) -> dict:
    """A practice set across this student's weakest topics, ignoring lessons.

    Body: {num_questions=5, types=["mcq","true_false"]}

    Picks the three lowest-mastery topics from topic_mastery and, where one
    carries a live misconception, targets it - so the set re-tests the belief
    the app already named instead of hoping it resurfaces by chance.
    """
    from app.services.quiz_generator import generate_adaptive_quiz as _generate

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    user_uuid = _generation_user(user)
    _spend_generation(db, user_uuid, "quiz", {"adaptive": True})

    try:
        return await _generate(
            db,
            user_id=user_uuid,
            num_questions=(payload or {}).get("num_questions", 5),
            types=tuple((payload or {}).get("types") or ("mcq", "true_false")),
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except RuntimeError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)
        ) from err


@router.post("/attempts/{attempt_id}/grade-open")
async def grade_open_answer(
    attempt_id: str,
    user: CurrentUser,
    payload: dict,
    db: Session | None = Depends(get_db),
) -> dict:
    """Grade one typed answer properly, with written feedback. (M1)

    Body: {question_id, answer}
    Returns: {is_correct, score_0_1, verdict, feedback, needs_review}

    `submit` grades short answers with a fast string match so a quiz never waits
    on a model. This is the careful version, for when a student wants to know
    WHY: a model reads the meaning, not the wording - but it may only mark an
    answer correct when it is confident and consistent, and otherwise abstains
    with `needs_review` rather than guessing. See services/open_grader.py.

    When the verdict is confident it also corrects the stored grade, so a right
    answer in the student's own words stops counting against them.
    """
    from app.services.open_grader import grade_open

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    try:
        attempt_uuid = uuid.UUID(attempt_id)
        user_uuid = uuid.UUID(str(user["id"]))
        question_uuid = uuid.UUID(str((payload or {}).get("question_id")))
    except (ValueError, KeyError, TypeError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="attempt_id and question_id must be valid ids.",
        ) from err

    attempt = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.id == attempt_uuid, QuizAttempt.user_id == user_uuid)
        .first()
    )
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    question = (
        db.query(Question)
        .filter(Question.id == question_uuid, Question.quiz_id == attempt.quiz_id)
        .first()
    )
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That question is not part of this attempt.",
        )

    answer = str((payload or {}).get("answer") or "")
    prompt, expected = question.prompt, question.correct_answer
    release_connection(db)
    result = await grade_open(prompt, expected, answer)

    if not result["needs_review"]:
        stored = (
            db.query(AttemptAnswer)
            .filter(
                AttemptAnswer.attempt_id == attempt.id,
                AttemptAnswer.question_id == question.id,
            )
            .first()
        )
        if stored is not None and stored.is_correct != result["is_correct"]:
            stored.is_correct = result["is_correct"]
            db.commit()

    return result
