"""Topic mastery and misconception capture. OWNER: Member 1. See plan.md 6.5 and 6.10.

The mastery score tells you a learner is struggling. The misconception tells you WHY,
and that is what the tutor explains. Capturing it is Tier 1 (plan.md 0.1).

Design note on abstention
-------------------------
The hard part is not producing a misconception - an LLM will happily produce one
for any wrong answer. The hard part is *declining* to. A wrong answer caused by a
typo, a misread, or a guess has no underlying false belief, and telling a student
they believe something they do not is worse than saying nothing at all. Every
guard in `_validate_misconception` exists to make abstention the easy default.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import difflib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("learnquest.mastery")

LEARNING_RATE = 0.3
DECAY_AFTER_DAYS = 7
DECAY_FACTOR = 0.95
MASTERY_MIN = 0.05
MASTERY_MAX = 0.99


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _get_or_create_row(db, user_id: uuid.UUID, topic_tag: str):
    """Fetch the topic_mastery row for this user/topic, creating it if absent."""
    from app.models.ai import TopicMastery

    row = (
        db.query(TopicMastery)
        .filter(TopicMastery.user_id == user_id, TopicMastery.topic_tag == topic_tag)
        .first()
    )
    if row is None:
        row = TopicMastery(
            user_id=user_id,
            topic_tag=topic_tag,
            mastery_score=0.5,
            attempts=0,
            correct=0,
        )
        db.add(row)
        db.flush()
    return row


# --------------------------------------------------------------------------- #
# Mastery score
# --------------------------------------------------------------------------- #


def update_mastery(db, user_id, topic_tag: str, correct: int, attempted: int) -> float:
    """Exponential moving average toward the observed correct rate.

        correct_rate = correct / attempted
        new = old + LEARNING_RATE * (correct_rate - old)
        if stale by more than DECAY_AFTER_DAYS: new *= DECAY_FACTOR
        clamp to [MASTERY_MIN, MASTERY_MAX]

    Describe this in the report as a simplified exponential-moving-average form of
    Bayesian Knowledge Tracing.
    """
    if attempted <= 0:
        raise ValueError("attempted must be greater than zero")

    uid = _as_uuid(user_id)
    if uid is None:
        raise ValueError(f"invalid user_id: {user_id!r}")

    row = _get_or_create_row(db, uid, topic_tag)
    old = float(row.mastery_score if row.mastery_score is not None else 0.5)

    # Decay first: a score that has not been exercised recently is less trustworthy.
    if row.last_practiced_at is not None:
        last = row.last_practiced_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if _now() - last > timedelta(days=DECAY_AFTER_DAYS):
            old *= DECAY_FACTOR

    correct_rate = max(0.0, min(1.0, correct / attempted))
    new = old + LEARNING_RATE * (correct_rate - old)
    new = max(MASTERY_MIN, min(MASTERY_MAX, new))

    row.mastery_score = new
    row.attempts = (row.attempts or 0) + attempted
    row.correct = (row.correct or 0) + correct
    row.last_practiced_at = _now()

    return new


# --------------------------------------------------------------------------- #
# Misconception capture
# --------------------------------------------------------------------------- #

MAX_MISCONCEPTION_CHARS = 200
CLEAR_AFTER_CORRECT_STREAK = 2
MIN_CONFIDENCE = 0.6

# Analysing every wrong answer would add one LLM round trip each and make quiz
# submission feel broken. Three is enough to find the dominant misunderstanding.
MAX_MISCONCEPTIONS_PER_SUBMISSION = 3

MISCONCEPTION_PROMPT = """A student answered a question incorrectly.

Question: {question}
Correct answer: {correct_answer}
The student answered: {user_answer}

Identify the single false belief that would lead someone to give THAT specific
answer.

Rules:
- Only answer if this wrong answer points to one clear, specific misunderstanding.
- Return null if the answer looks like a typo, a slip, a random guess, a blank, or
  if you genuinely cannot tell what they were thinking.
- Never invent a belief to be helpful. Returning null is a correct, expected answer
  and happens often.
- Do not restate the correct answer. Describe what the student wrongly believes.
- Write it as "You believe ..." in plain English, under {max_chars} characters.

Return ONLY JSON:
{{"misconception": "You believe ..." or null, "confidence": 0.0 to 1.0}}"""

# Phrases that mean the model declined, even though it returned a string.
_REFUSAL_MARKERS = (
    "cannot determine",
    "can't determine",
    "cannot tell",
    "can't tell",
    "unclear",
    "no misconception",
    "not enough information",
    "insufficient",
    "unable to",
    "n/a",
    "none",
    "null",
)


def _extract_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _validate_misconception(payload: Any, correct_answer: str) -> str | None:
    """Return a usable misconception, or None to abstain.

    Abstention is the default: anything ambiguous returns None.
    """
    if not isinstance(payload, dict):
        return None

    raw = payload.get("misconception")
    if raw is None or not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    # The model said "I don't know" in prose rather than returning null.
    lowered = text.lower().strip(" .\"'")
    if lowered in _REFUSAL_MARKERS or any(m in lowered for m in _REFUSAL_MARKERS[:8]):
        return None

    # Too long to be a crisp belief, or too short to be one at all.
    if len(text) > MAX_MISCONCEPTION_CHARS or len(text) < 12:
        return None

    try:
        confidence = float(payload.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    if confidence < MIN_CONFIDENCE:
        return None

    # Guard against the model simply echoing the correct answer back, which
    # tells the student nothing about what they got wrong.
    if correct_answer:
        similarity = difflib.SequenceMatcher(
            None, text.lower(), str(correct_answer).lower()
        ).ratio()
        if similarity > 0.75:
            return None

    return text


async def capture_misconception(db, user_id, topic_tag: str, question, user_answer: str):
    """Ask the LLM what the learner believes that is untrue, and store it.

    Returns None when no specific belief can be identified - and storing None is the
    right outcome. An invented misconception tells the learner they think something
    they do not, which is worse than saying nothing (plan.md 6.10).
    """
    uid = _as_uuid(user_id)
    if uid is None:
        return None

    # `question` may be a dict from the quiz payload or a plain string.
    if isinstance(question, dict):
        prompt_text = question.get("prompt") or question.get("question") or ""
        correct_answer = question.get("correct_answer") or question.get("answer") or ""
    else:
        prompt_text = str(question or "")
        correct_answer = ""

    if not prompt_text.strip() or not str(user_answer or "").strip():
        return None  # nothing to reason about

    prompt = MISCONCEPTION_PROMPT.format(
        question=prompt_text.strip()[:1000],
        correct_answer=str(correct_answer).strip()[:500] or "(not supplied)",
        user_answer=str(user_answer).strip()[:500],
        max_chars=MAX_MISCONCEPTION_CHARS,
    )

    try:
        from app.services.llm_client import get_llm

        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,  # low: we want a careful reading, not creativity
            max_tokens=300,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001 - never fail a submission over this
        logger.warning("Misconception LLM call failed for %s: %s", topic_tag, exc)
        return None

    misconception = _validate_misconception(_extract_json(raw), correct_answer)
    if misconception is None:
        logger.info("No misconception identified for topic=%s (abstained)", topic_tag)
        return None

    row = _get_or_create_row(db, uid, topic_tag)
    row.misconception = misconception
    row.misconception_updated_at = _now()
    row.misconception_correct_streak = 0  # a fresh misconception is active again
    row.misconception_cleared_at = None

    logger.info("Captured misconception topic=%s: %s", topic_tag, misconception[:80])
    return misconception


def register_correct_answer(db, user_id, topic_tag: str) -> str:
    """Advance the decay of a stored misconception after a correct answer.

    Returns the resulting status: 'active', 'fading', 'cleared' or 'none'.
    """
    uid = _as_uuid(user_id)
    if uid is None:
        return "none"

    row = _get_or_create_row(db, uid, topic_tag)
    if not row.misconception or row.misconception_cleared_at is not None:
        return "none" if not row.misconception else "cleared"

    row.misconception_correct_streak = (row.misconception_correct_streak or 0) + 1

    if row.misconception_correct_streak >= CLEAR_AFTER_CORRECT_STREAK:
        # Keep the text - the misconception map shows what a student has
        # overcome, not just what they are still getting wrong.
        row.misconception_cleared_at = _now()
        logger.info("Misconception cleared topic=%s", topic_tag)
        return "cleared"

    return "fading"


def misconception_status(row) -> str:
    """Derive display status from stored fields. Nothing to keep in sync."""
    if not row.misconception:
        return "none"
    if row.misconception_cleared_at is not None:
        return "cleared"
    if (row.misconception_correct_streak or 0) > 0:
        return "fading"
    return "active"


# --------------------------------------------------------------------------- #
# quiz.submitted integration
# --------------------------------------------------------------------------- #


def _load_answers_from_attempt(db, attempt_id) -> list[dict[str, Any]]:
    """Rebuild the `answers` list by reading `attempt_answers` for this attempt.

    M2's submit endpoint emits only the counts (quiz_id / attempt_id / score /
    correct / total). That is enough for XP but carries nothing to reason about,
    so without this the misconception engine would receive an empty list and
    silently do nothing on every submission.

    The rows already hold everything needed: `attempt_answers.user_answer`,
    `.is_correct` and `.topic_tag` (copied at submit time), and the joined
    `questions` row supplies the prompt and the correct answer. Reading them
    here keeps the fix inside M1's own file - M2's router does not change.
    """
    aid = _as_uuid(attempt_id)
    if aid is None or db is None:
        return []

    try:
        from app.models.quiz import AttemptAnswer, Question

        rows = (
            db.query(AttemptAnswer, Question)
            .outerjoin(Question, Question.id == AttemptAnswer.question_id)
            .filter(AttemptAnswer.attempt_id == aid)
            .all()
        )
    except Exception as exc:  # noqa: BLE001 - a submission must never fail here
        logger.warning("Could not load attempt_answers for %s: %s", attempt_id, exc)
        return []

    answers: list[dict[str, Any]] = []
    for answer, question in rows:
        answers.append(
            {
                "topic_tag": answer.topic_tag
                or (question.topic_tag if question is not None else None),
                "prompt": question.prompt if question is not None else "",
                "correct_answer": question.correct_answer if question is not None else "",
                "user_answer": answer.user_answer or "",
                "is_correct": bool(answer.is_correct),
            }
        )
    return answers


def _run_coroutine_blocking(coro):
    """Run an async coroutine from a synchronous event handler.

    `emit()` is synchronous. A sync FastAPI endpoint runs in a worker thread with
    no event loop, so `asyncio.run` is fine there. If a loop *is* already running
    we hand the coroutine to a separate thread and wait, rather than fire-and-
    forget - the caller's DB session must still be open when we write to it.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _analyse_answers(db, user_id, wrong: list[dict[str, Any]]) -> list[str]:
    """Capture misconceptions for several wrong answers concurrently.

    Concurrent so that three wrong answers cost roughly one LLM round trip
    rather than three sequential ones.
    """
    results = await asyncio.gather(
        *(
            capture_misconception(
                db,
                user_id,
                item.get("topic_tag") or "",
                item,
                item.get("user_answer") or item.get("answer") or "",
            )
            for item in wrong
        ),
        return_exceptions=True,
    )
    captured = []
    for res in results:
        if isinstance(res, Exception):
            logger.warning("Misconception capture raised: %s", res)
        elif res:
            captured.append(res)
    return captured


def handle_quiz_submitted(db, user_id, payload: dict[str, Any]) -> dict[str, Any]:
    """Update mastery per topic, then capture misconceptions for wrong answers.

    Expected payload (emitted by M2's quiz submit endpoint):

        {
          "quiz_id": ..., "attempt_id": ...,
          "correct_count": 3, "total_questions": 5,
          "answers": [
            {"topic_tag": "dbms.sql_joins",
             "prompt": "Which join ...?",
             "correct_answer": "INNER JOIN",
             "user_answer": "FULL JOIN",
             "is_correct": false},
            ...
          ]
        }

    `answers` is optional. When it is absent but `attempt_id` is present we read
    the rows back from `attempt_answers` ourselves, so the engine works whether or
    not the emitter includes them.
    """
    answers = payload.get("answers") or payload.get("questions") or []
    if not isinstance(answers, list):
        answers = []

    if not answers and payload.get("attempt_id"):
        answers = _load_answers_from_attempt(db, payload["attempt_id"])
        if answers:
            logger.info(
                "quiz.submitted carried no answers; loaded %d from attempt_answers "
                "(attempt_id=%s)",
                len(answers),
                payload["attempt_id"],
            )

    # --- mastery, per topic ---
    per_topic: dict[str, list[int]] = {}
    for item in answers:
        if not isinstance(item, dict):
            continue
        tag = item.get("topic_tag")
        if not tag:
            continue
        correct, attempted = per_topic.setdefault(tag, [0, 0])
        per_topic[tag] = [correct + (1 if item.get("is_correct") else 0), attempted + 1]

    for tag, (correct, attempted) in per_topic.items():
        try:
            update_mastery(db, user_id, tag, correct, attempted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("update_mastery failed for %s: %s", tag, exc)

    # --- capture misconceptions for wrong answers ---
    wrong = [
        item
        for item in answers
        if isinstance(item, dict) and not item.get("is_correct") and item.get("topic_tag")
    ]
    wrong_topics = {item["topic_tag"] for item in wrong}
    wrong = wrong[:MAX_MISCONCEPTIONS_PER_SUBMISSION]

    # --- decay existing misconceptions on correct answers ---
    #
    # A topic the learner also got WRONG in this same submission is skipped. A
    # four-question quiz on one topic would otherwise run the decay three times
    # off the questions they happened to get right and clear the very
    # misconception the fourth question just revealed - and if the re-capture
    # call then fails, the belief is marked "overcome" on the evidence of a
    # quiz they did not pass. Getting one wrong is not mastery.
    for item in answers:
        if not (isinstance(item, dict) and item.get("is_correct")):
            continue
        tag = item.get("topic_tag")
        if not tag or tag in wrong_topics:
            continue
        try:
            register_correct_answer(db, user_id, tag)
        except Exception as exc:  # noqa: BLE001
            logger.warning("register_correct_answer failed: %s", exc)

    captured: list[str] = []
    if wrong:
        try:
            captured = _run_coroutine_blocking(_analyse_answers(db, user_id, wrong))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Misconception analysis failed: %s", exc)

    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not commit mastery updates: %s", exc)
        db.rollback()

    return {
        "topics_updated": len(per_topic),
        "misconceptions_captured": len(captured),
        "misconceptions": captured,
    }


# Registered here rather than in xp_engine.py (Member 4's file). Multiple
# handlers may subscribe to the same event; both this and the XP handler run.
from app.services.events import register_handler  # noqa: E402


@register_handler("quiz.submitted")
def _on_quiz_submitted(db, user_id, payload: dict[str, Any]) -> dict[str, Any]:
    return handle_quiz_submitted(db, user_id, payload or {})
