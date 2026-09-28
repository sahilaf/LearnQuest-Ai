"""Grade a typed, free-text answer. OWNER: Member 1. See plan.md 6.4.

Free text is where the misconception engine gets its best signal - a multiple
choice pick says *which* wrong answer, a sentence says *why*. It is also where
an over-generous grader does the most damage, because a student told they are
right stops trying to understand.

So the rules, in order:

  1. An empty answer is wrong, without asking anybody.
  2. An answer that plainly contains the expected one is right, deterministically.
     No model is needed to see that, and none is trusted to overrule it.
  3. Otherwise a model judges it - and its verdict is only accepted when it is
     internally consistent and confident. A judge that errors, contradicts its
     own score, or is unsure ABSTAINS: `needs_review` is set and the answer is
     not marked correct. Being wrongly told "correct" is worse than waiting.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("learnquest.opengrader")

PASS_SCORE = 0.7
MIN_CONFIDENCE = 0.6

GRADE_PROMPT = """Grade a student's typed answer against the expected answer.

Question: {question}
Expected answer: {expected}
Student's answer: {given}

Judge the MEANING, not the wording, spelling or length. A correct idea in the
student's own words is correct. A fluent answer that gets the idea wrong is not.

Return ONLY JSON:
{{"verdict": "correct" | "partial" | "incorrect",
  "score": 0.0 to 1.0,
  "confidence": 0.0 to 1.0,
  "feedback": "one or two sentences, addressed to the student, saying what is
               right and what is missing or wrong. Never reveal the full
               expected answer if they got it wrong - point them at the gap."}}"""


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower()).strip()


def _extract_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _result(is_correct, score, feedback, *, verdict, needs_review=False, graded_by="rule"):
    return {
        "is_correct": bool(is_correct),
        "score_0_1": round(max(0.0, min(1.0, float(score))), 2),
        "verdict": verdict,
        "feedback": feedback,
        "needs_review": needs_review,
        "graded_by": graded_by,
    }


def grade_choice(given: str, expected: str) -> dict[str, Any]:
    """Multiple choice and true/false: an exact comparison, no model."""
    correct = _normalise(given) == _normalise(expected) and bool(_normalise(given))
    return _result(
        correct,
        1.0 if correct else 0.0,
        "Correct." if correct else "Not quite - that is not the right option.",
        verdict="correct" if correct else "incorrect",
    )


async def grade_open(question: str, expected: str, given: str) -> dict[str, Any]:
    """Grade a typed answer. Never raises; abstains rather than guessing."""
    answer = str(given or "").strip()
    if not answer:
        return _result(False, 0.0, "No answer was given.", verdict="incorrect")

    g, e = _normalise(answer), _normalise(expected)
    if e and (g == e or (len(e) >= 4 and e in g)):
        return _result(True, 1.0, "Correct.", verdict="correct")

    try:
        from app.services.llm_client import get_llm

        raw = await get_llm().complete(
            [
                {
                    "role": "user",
                    "content": GRADE_PROMPT.format(
                        question=str(question or "")[:800],
                        expected=str(expected or "")[:500],
                        given=answer[:1500],
                    ),
                }
            ],
            temperature=0.0,  # grading should not be creative
            max_tokens=400,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Open grading call failed, abstaining: %s", exc)
        return _result(
            False,
            0.0,
            "We could not grade this automatically just now, so it is marked for review.",
            verdict="needs_review",
            needs_review=True,
            graded_by="abstained",
        )

    data = _extract_json(raw) or {}
    verdict = str(data.get("verdict") or "").strip().lower()
    feedback = str(data.get("feedback") or "").strip()[:600]
    try:
        score = float(data.get("score", 0))
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        score, confidence = 0.0, 0.0

    if verdict not in ("correct", "partial", "incorrect") or not feedback:
        return _result(
            False, 0.0,
            "We could not grade this automatically, so it is marked for review.",
            verdict="needs_review", needs_review=True, graded_by="abstained",
        )

    # An unsure judge does not get to decide.
    if confidence < MIN_CONFIDENCE:
        return _result(
            False, min(score, PASS_SCORE - 0.01), feedback,
            verdict="needs_review", needs_review=True, graded_by="abstained",
        )

    # The verdict and the score must agree. "correct" with a score of 0.2 means
    # the model has not actually decided, so take the conservative reading.
    is_correct = verdict == "correct" and score >= PASS_SCORE
    if not is_correct:
        score = min(score, PASS_SCORE - 0.01)

    return _result(is_correct, score, feedback, verdict=verdict, graded_by="model")
