"""Teach-Back: the student teaches Redwan out of their own misconception.

OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning). See plan.md 6.10.

This is the protege effect made literal, and it is the project's novel core.
A normal tutor explains until the student nods. Here the direction reverses:

  1. `capture_misconception()` (services/mastery.py) has already named the false
     belief behind a wrong answer, in the student's own terms.
  2. Redwan is seeded with *that* belief and argues from it - confidently, the way
     someone who actually holds it would.
  3. The student has to talk him out of it.
  4. Redwan then re-takes the question the student originally got wrong, reasoning
     only from what he was just taught. **His score is the student's grade.**

Step 4 is what makes it a measurement rather than a chat. You have only taught
something when the learner can use it without you standing there.

Design note on grading
----------------------
The obvious failure is a model that marks itself correct to be agreeable. Two
defences: a deterministic match runs first and can pass a session without any
model judgement at all, and the LLM judge is only consulted when that is
inconclusive. A judge that errors, times out or returns something unparseable
fails the retake - it never passes by default.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import release_connection

logger = logging.getLogger("learnquest.teachback")

# Redwan must clear this to count as taught.
PASS_SCORE = 70

# After this many failed retakes the session closes. Unlimited retries would
# let a student brute-force the phrasing instead of explaining the idea.
MAX_RETAKES = 3

# Hints a student can ask for in one session, each more specific than the last.
MAX_HINTS = 3

# A message shorter than this cannot be an explanation. Checked before the LLM
# so "idk" costs nothing and still gets a push-back.
MIN_EXPLANATION_CHARS = 25

# Cannot live in xp_engine.XP_AWARDS - that is Member 4's file.
TEACHBACK_XP = 40


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Parse a JSON object out of a model reply, fenced or not."""
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


async def _ask_llm(prompt: str, *, max_tokens: int = 500, temperature: float = 0.4) -> str:
    from app.services.llm_client import get_llm

    return await get_llm().complete(
        [{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

NOVA_OPENING_PROMPT = """You are Redwan, a student who genuinely holds this false belief:

"{misconception}"

You are about to be taught about: {topic}
The question you got wrong: {question}

Open the conversation. In 2-3 sentences:
- State your belief plainly, as something you are confident about. Do not hedge,
  and never say you are wrong or confused - you do not know you are wrong.
- Then ask ONE specific question that follows from your belief.

Stay in character as a learner. Do not teach. Do not mention being an AI.

Return ONLY JSON:
{{"opening": "..."}}"""

NOVA_REPLY_PROMPT = """You are Redwan, a student who holds this false belief:

"{misconception}"

Topic: {topic}
The question you got wrong: {question}

Conversation so far:
{transcript}

The student just told you:
"{explanation}"

Decide honestly whether that explanation actually addresses your false belief.

- If it is vague, hand-waving, just asserts you are wrong, or only restates the
  right answer without explaining WHY your belief fails: push back. Say what you
  still do not follow, in your own words. Set "convinced": false.
- If it genuinely explains why your belief is wrong: say what changed in your
  understanding and what you now think. Set "convinced": true.
- Never pretend to be convinced to be encouraging. Being too easily convinced
  makes the whole exercise worthless.
- Ask at most one follow-up question. Stay under 70 words. Never lecture.

Return ONLY JSON:
{{"reply": "...", "convinced": true or false}}"""

NOVA_RETAKE_PROMPT = """You are Redwan. You are re-taking a question you previously got wrong.

Originally you believed: "{misconception}"

A student has just tried to teach you. This is everything they said:
{teaching}

Now answer this question using ONLY what they taught you plus your own reasoning.

Question: {question}
{options_block}

Rules:
- Being TOLD an answer is not the same as understanding it. If the student
  simply asserted the right answer, or restated the definition, without
  explaining WHY your belief is wrong, then you have learned nothing: answer
  the way your original belief would lead you to answer.
- Only give the answer they stated if they explained the mechanism well enough
  that you could have reached it yourself.
- If their explanation did not actually fix your understanding, answer the way
  your original belief would lead you to answer. Do not guess at what the
  expected answer is - reason from what you now believe.
- Do not mention the student, the lesson or this conversation in your answer.
- Answer in under 40 words.

Return ONLY JSON:
{{"answer": "...", "reasoning": "one sentence on why you answered that"}}"""

GRADE_PROMPT = """Grade one answer against the expected answer.

Question: {question}
Expected answer: {expected}
Given answer: {given}

Is the given answer correct in substance? Ignore wording, spelling and length.
Judge the meaning only.

Return ONLY JSON:
{{"correct": true or false, "score": 0 to 100, "why": "one short sentence"}}"""

HINT_PROMPT = """A student is trying to teach a classmate out of a false belief, and is stuck.

The classmate's false belief: "{misconception}"
The question the classmate will re-take: {question}
The correct answer (NEVER state, quote or paraphrase it): {answer}

What the student has said so far:
{teaching}

Give hint number {level} of 3. Hints get more specific:
1 = point to the concept they should explain (which idea is the belief getting wrong).
2 = suggest a concrete example or case that shows where the belief breaks.
3 = name the mechanism they still need to explain, as a question to answer.

Rules:
- Never give the correct answer, an option letter, or a sentence that contains it.
- Speak to the student ("Try explaining..."), in one or two sentences, under 45 words.
- Build on what they already said; do not repeat an earlier hint.

Return ONLY JSON:
{{"hint": "..."}}"""

# Used when the model is unavailable or its hint gives the answer away.
FALLBACK_HINTS = (
    "Start from his belief: what does it predict for this exact question, and where does "
    "that prediction go wrong?",
    "Try a small, concrete example - a couple of rows, a few values - and walk him through "
    "what really happens step by step.",
    "Explain the rule behind it, not just the result: why does it work that way? Say the "
    "'because' out loud.",
)

GENERATE_QUESTION_PROMPT = """Write one question that a person holding this false belief would get wrong:

"{misconception}"

Topic: {topic}

The question must have a single, short, unambiguous correct answer, and someone
holding the false belief must plausibly give a different answer.

Return ONLY JSON:
{{"prompt": "...", "correct_answer": "..."}}"""


# --------------------------------------------------------------------------- #
# Picking what to teach
# --------------------------------------------------------------------------- #


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower()).strip()


def pick_misconception(db, user_id, topic_tag: str | None = None):
    """The TopicMastery row this session will work on, or None.

    Cleared misconceptions are skipped: there is nothing left to teach. When no
    topic is named we take the most recently captured one still standing.
    """
    from app.models.ai import TopicMastery

    uid = _as_uuid(user_id)
    if uid is None or db is None:
        return None

    query = db.query(TopicMastery).filter(
        TopicMastery.user_id == uid,
        TopicMastery.misconception.isnot(None),
        TopicMastery.misconception_cleared_at.is_(None),
    )
    if topic_tag:
        query = query.filter(TopicMastery.topic_tag == topic_tag)

    return query.order_by(
        TopicMastery.misconception_updated_at.desc().nullslast()
    ).first()


def _find_wrong_answer(db, user_id, topic_tag: str, question_id=None):
    """The question behind this misconception, else the most recent wrong one.

    `question_id` is the question whose wrong answer produced the belief; it is
    used when known, so the belief and the question always belong together.

    Teaching lands better against the actual question they got wrong than
    against a freshly invented one, so this is tried first.
    """
    from app.models.quiz import AttemptAnswer, Question, QuizAttempt

    uid = _as_uuid(user_id)
    if uid is None:
        return None

    qid = _as_uuid(question_id)
    if qid is not None:
        exact = db.query(Question).filter(Question.id == qid).first()
        if exact is not None:
            return exact

    try:
        return (
            db.query(Question)
            .join(AttemptAnswer, AttemptAnswer.question_id == Question.id)
            .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
            .filter(
                QuizAttempt.user_id == uid,
                AttemptAnswer.is_correct.is_(False),
                AttemptAnswer.topic_tag == topic_tag,
            )
            .order_by(QuizAttempt.submitted_at.desc().nullslast())
            .first()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not look up a wrong answer for %s: %s", topic_tag, exc)
        return None


async def _invent_question(misconception: str, topic_tag: str) -> dict[str, Any] | None:
    """Fallback when no stored wrong answer exists for this topic."""
    try:
        raw = await _ask_llm(
            GENERATE_QUESTION_PROMPT.format(
                misconception=misconception[:300], topic=topic_tag
            ),
            max_tokens=300,
            temperature=0.3,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not generate a Teach-Back question: %s", exc)
        return None

    data = _extract_json(raw) or {}
    prompt = str(data.get("prompt") or "").strip()
    answer = str(data.get("correct_answer") or "").strip()
    if len(prompt) < 10 or not answer:
        return None
    return {"prompt": prompt[:1000], "correct_answer": answer[:500]}


# --------------------------------------------------------------------------- #
# Session lifecycle
# --------------------------------------------------------------------------- #


def _transcript(session, limit: int = 8) -> str:
    # Hints are for the student only - Redwan must never "hear" them.
    turns = [t for t in (session.turns or []) if t.get("role") in ("nova", "student")][-limit:]
    if not turns:
        return "(nothing yet)"
    speaker = {"nova": "Redwan", "student": "Student"}
    return "\n".join(
        f"{speaker.get(t.get('role'), 'Student')}: {t.get('content', '')}"
        for t in turns
    )


def _append_turn(session, role: str, content: str) -> None:
    """Append a turn. Reassigns the list so SQLAlchemy sees the JSON change."""
    session.turns = list(session.turns or []) + [
        {"role": role, "content": content, "at": _now().isoformat()}
    ]


async def start_session(db, user_id, topic_tag: str | None = None):
    """Open a Teach-Back round. Returns (session, error_code).

    error_code is None on success, otherwise one of:
      'no_misconception' - nothing to teach out of yet
      'no_question'      - a misconception with nothing to test it against
    """
    from app.models.ai import TeachBackSession

    row = pick_misconception(db, user_id, topic_tag)
    if row is None:
        return None, "no_misconception"

    # Pressing "Teach" again on a topic already being taught resumes that
    # session. Each press used to open a fresh one (and spend a model call on a
    # new opening), so a student who navigated away lost their progress and
    # piled up abandoned sessions.
    open_session = (
        db.query(TeachBackSession)
        .filter(
            TeachBackSession.user_id == _as_uuid(user_id),
            TeachBackSession.topic_tag == row.topic_tag,
            TeachBackSession.misconception == row.misconception,
            TeachBackSession.status == "teaching",
        )
        .order_by(TeachBackSession.created_at.desc())
        .first()
    )
    if open_session is not None:
        return open_session, None

    question = _find_wrong_answer(
        db, user_id, row.topic_tag, getattr(row, "misconception_question_id", None)
    )
    if question is not None:
        q_id = question.id
        q_prompt = question.prompt
        q_answer = question.correct_answer
        q_options = question.options
    else:
        release_connection(db)
        invented = await _invent_question(row.misconception, row.topic_tag)
        if invented is None:
            return None, "no_question"
        q_id, q_prompt, q_answer, q_options = (
            None,
            invented["prompt"],
            invented["correct_answer"],
            None,
        )

    session = TeachBackSession(
        user_id=_as_uuid(user_id),
        topic_tag=row.topic_tag,
        misconception=row.misconception,
        question_id=q_id,
        question_prompt=q_prompt,
        question_correct_answer=q_answer,
        question_options=q_options,
        status="teaching",
        turns=[],
    )

    release_connection(db)
    opening = await _nova_opening(row.misconception, row.topic_tag, q_prompt)
    _append_turn(session, "nova", opening)

    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info(
        "Teach-Back opened user=%s topic=%s", user_id, row.topic_tag
    )
    return session, None


async def _nova_opening(misconception: str, topic_tag: str, question: str) -> str:
    """Redwan's first line. Falls back to stating the belief verbatim."""
    fallback = (
        f"{misconception} That is how I have always read it - "
        f"so why would that not work here?"
    )
    try:
        raw = await _ask_llm(
            NOVA_OPENING_PROMPT.format(
                misconception=misconception[:300],
                topic=topic_tag,
                question=question[:500],
            ),
            max_tokens=300,
            temperature=0.6,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redwan opening failed, using fallback: %s", exc)
        return fallback

    data = _extract_json(raw) or {}
    opening = str(data.get("opening") or "").strip()
    return opening[:600] if len(opening) >= 20 else fallback


def _looks_vague(text: str) -> bool:
    """Catch non-explanations before spending an LLM call on them.

    Deliberately narrow - it only fires on things that cannot be an explanation
    under any reading. Judging actual substance is the model's job.
    """
    clean = _normalise(text)
    if len(clean) < MIN_EXPLANATION_CHARS:
        return True
    dismissals = {
        "no", "yes", "wrong", "youre wrong", "you are wrong", "thats wrong",
        "that is wrong", "nope", "idk", "i dont know", "i do not know",
        "just because", "because", "its obvious", "it is obvious", "look it up",
    }
    return clean in dismissals


async def student_turn(db, session, explanation: str) -> dict[str, Any]:
    """The student teaches. Redwan pushes back or concedes.

    Returns {"reply", "convinced", "can_retake"}.
    """
    text = str(explanation or "").strip()
    _append_turn(session, "student", text[:2000])

    if _looks_vague(text):
        reply = (
            "That does not really tell me anything I can use. "
            "Can you walk me through why what I said is wrong?"
        )
        _append_turn(session, "nova", reply)
        db.commit()
        return {"reply": reply, "convinced": False, "can_retake": False}

    release_connection(db)  # also saves the student's turn before Redwan answers
    try:
        raw = await _ask_llm(
            NOVA_REPLY_PROMPT.format(
                misconception=session.misconception[:300],
                topic=session.topic_tag,
                question=session.question_prompt[:500],
                transcript=_transcript(session),
                explanation=text[:1500],
            ),
            max_tokens=400,
            temperature=0.5,
        )
        data = _extract_json(raw) or {}
        reply = str(data.get("reply") or "").strip()
        convinced = bool(data.get("convinced"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redwan reply failed: %s", exc)
        reply, convinced = "", False

    if len(reply) < 10:
        # Never drop the student's turn on the floor; keep the loop moving.
        reply = "Let me make sure I follow - can you say that another way?"
        convinced = False

    _append_turn(session, "nova", reply[:800])
    db.commit()

    # The retake is always available once there is something to reason from.
    # Gating it on `convinced` would let Redwan refuse to be examined.
    taught = sum(1 for t in (session.turns or []) if t.get("role") == "student")
    return {"reply": reply, "convinced": convinced, "can_retake": taught >= 1}


# --------------------------------------------------------------------------- #
# The retake - Redwan's score is the student's grade
# --------------------------------------------------------------------------- #


def _deterministic_match(given: str, expected: str, options: list[str] | None) -> bool | None:
    """True/False when the comparison is unambiguous, None to defer to the judge.

    Runs before the model so a clean pass never depends on one, and so an
    obviously wrong answer cannot be talked into a pass.
    """
    g, e = _normalise(given), _normalise(expected)
    if not g or not e:
        return None
    if g == e:
        return True

    # Multiple choice: the answer must name exactly one option, and it must be
    # the right one.
    if options:
        named = [o for o in options if _normalise(o) and _normalise(o) in g]
        if len(named) == 1:
            return _normalise(named[0]) == e
        if len(named) > 1:
            # "either LEFT JOIN or INNER JOIN" is not an answer. Return before
            # the containment check below, which would otherwise see the correct
            # option inside the hedge and pass it.
            return None

    # A short expected answer quoted inside a longer one ("INNER JOIN, because...").
    if len(e) >= 4 and e in g:
        return True

    if difflib.SequenceMatcher(None, g, e).ratio() > 0.9:
        return True
    return None


async def _grade(question: str, expected: str, given: str, options) -> dict[str, Any]:
    """Score `given` against `expected`. Abstains to a fail, never to a pass."""
    verdict = _deterministic_match(given, expected, options if isinstance(options, list) else None)
    if verdict is True:
        return {"score": 100, "correct": True, "why": "Matches the expected answer."}
    if verdict is False:
        return {"score": 0, "correct": False, "why": "Names the wrong option."}

    try:
        raw = await _ask_llm(
            GRADE_PROMPT.format(
                question=question[:500], expected=expected[:300], given=given[:500]
            ),
            max_tokens=250,
            temperature=0.0,
        )
        data = _extract_json(raw) or {}
        score = int(float(data.get("score", 0)))
        correct = bool(data.get("correct"))
        why = str(data.get("why") or "").strip()[:200]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Grading call failed, failing the retake: %s", exc)
        return {"score": 0, "correct": False, "why": "Could not grade this answer."}

    score = max(0, min(100, score))
    # The two fields must agree. A model that says correct=true with score 20
    # has not actually decided; take the conservative reading.
    if correct and score < PASS_SCORE:
        correct = False
    if not correct:
        score = min(score, PASS_SCORE - 1)

    return {"score": score, "correct": correct, "why": why or "Judged on meaning."}


def _answer_was_handed_over(student_turns: list[str], correct_answer: str) -> bool:
    """True when the student quoted the answer without explaining anything.

    Containment alone is not enough to judge: a real explanation often quotes
    the answer on its way to explaining it. What separates the two is how much
    else they wrote, so the test is "the answer, and almost nothing besides".
    """
    answer = _normalise(correct_answer)
    if len(answer) < 4:
        return False

    said = _normalise(" ".join(student_turns))
    if answer not in said:
        return False

    remainder = said.replace(answer, " ").split()
    return len(remainder) < 25


async def retake(db, session) -> dict[str, Any]:
    """Redwan re-takes the question. His score is the student's grade."""
    from app.services.events import emit
    from app.services.mastery import register_correct_answer

    if session.status in ("passed", "failed"):
        return {"error": "session_closed", "status": session.status}

    student_turns = [
        str(t.get("content", ""))
        for t in (session.turns or [])
        if t.get("role") == "student"
    ]
    teaching = "\n".join(f"- {t}" for t in student_turns)
    if not teaching.strip():
        return {"error": "nothing_taught"}

    # Handing over the answer is not teaching. A model that can see the correct
    # answer in its own context will repeat it back and score 100, which would
    # let a student pass by typing the answer instead of explaining it - and
    # explaining it is the entire exercise. Saying so explicitly is what makes
    # the retake a measurement rather than a formality.
    if _answer_was_handed_over(student_turns, session.question_correct_answer):
        teaching += (
            "\n\nNOTE: the student stated the correct answer but did not explain "
            "why your belief is wrong. Being told an answer teaches you nothing."
        )

    options = session.question_options if isinstance(session.question_options, list) else None
    options_block = (
        "Options: " + " | ".join(str(o) for o in options) if options else ""
    )
    release_connection(db)

    try:
        raw = await _ask_llm(
            NOVA_RETAKE_PROMPT.format(
                misconception=session.misconception[:300],
                teaching=teaching[:2000],
                question=session.question_prompt[:500],
                options_block=options_block,
            ),
            max_tokens=350,
            temperature=0.3,
        )
        data = _extract_json(raw) or {}
        nova_answer = str(data.get("answer") or "").strip()
        nova_reasoning = str(data.get("reasoning") or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redwan retake failed: %s", exc)
        nova_answer, nova_reasoning = "", ""

    if not nova_answer:
        # No answer is not a pass. Do not consume a retake for our own failure.
        return {"error": "nova_unavailable"}

    grade = await _grade(
        session.question_prompt,
        session.question_correct_answer,
        nova_answer,
        options,
    )

    session.retakes = (session.retakes or 0) + 1
    session.nova_answer = nova_answer[:1000]
    session.nova_reasoning = nova_reasoning[:500]
    session.nova_score = grade["score"]

    passed = grade["correct"] and grade["score"] >= PASS_SCORE
    xp_awarded = 0

    if passed:
        session.status = "passed"
        session.completed_at = _now()
        # A successful Teach-Back is evidence the belief is going, so it feeds
        # the same active -> fading -> cleared decay as a correct quiz answer.
        try:
            register_correct_answer(db, session.user_id, session.topic_tag)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not decay misconception after Teach-Back: %s", exc)
    elif session.retakes >= MAX_RETAKES:
        session.status = "failed"
        session.completed_at = _now()

    db.commit()
    db.refresh(session)

    if passed:
        results = emit(
            db=db,
            user_id=session.user_id,
            event_type="teachback.completed",
            payload={
                "session_id": str(session.id),
                "topic_tag": session.topic_tag,
                "score": session.nova_score,
                "retakes": session.retakes,
            },
        )
        for result in results:
            if isinstance(result, dict) and result.get("xp_awarded"):
                xp_awarded = result["xp_awarded"]
                break

    return {
        "nova_answer": nova_answer,
        "nova_reasoning": nova_reasoning,
        "score": grade["score"],
        "passed": passed,
        "why": grade["why"],
        "correct_answer": session.question_correct_answer if session.status in ("passed", "failed") else None,
        "status": session.status,
        "retakes": session.retakes,
        "retakes_left": max(0, MAX_RETAKES - session.retakes),
        "xp_awarded": xp_awarded,
    }


# --------------------------------------------------------------------------- #
# XP
# --------------------------------------------------------------------------- #

# Registered here, not in xp_engine.py, because that file belongs to Member 4.
# `award_xp` is imported and called, never edited - the XP audit row is still
# written by M4's engine, so the ledger stays in one place.
from app.services.events import register_handler  # noqa: E402


@register_handler("teachback.completed")
def _on_teachback_completed(db, user_id, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.xp_engine import award_xp

    return award_xp(
        db=db,
        user_id=user_id,
        amount=TEACHBACK_XP,
        reason="Taught Redwan out of a misconception",
        event_type="teachback.completed",
        ref_type="teachback",
        ref_id=payload.get("session_id"),
        metadata={
            "topic_tag": payload.get("topic_tag"),
            "score": payload.get("score"),
            "retakes": payload.get("retakes"),
        },
    )


# --------------------------------------------------------------------------- #
# Help while teaching: hints, and what to study first
# --------------------------------------------------------------------------- #


def hints_used(session) -> int:
    return sum(1 for t in (session.turns or []) if t.get("role") == "hint")


def _gives_answer_away(hint: str, answer: str) -> bool:
    """True when a hint contains the answer itself.

    Short generic answers (True / False / a single letter) are skipped: the
    word "false" in a sentence is not the answer being handed over.
    """
    a = _normalise(answer)
    if len(a) < 4 or a in ("true", "false"):
        return False
    return a in _normalise(hint)


async def give_hint(db, session) -> dict[str, Any]:
    """The next hint for the student. Never shown to Redwan, never the answer.

    Returns {"hint", "level", "hints_left"} or {"error": ...}.
    """
    if session.status in ("passed", "failed"):
        return {"error": "session_closed", "status": session.status}
    level = hints_used(session) + 1
    if level > MAX_HINTS:
        return {"error": "no_hints_left"}

    teaching = "\n".join(
        f"- {t.get('content', '')}" for t in (session.turns or []) if t.get("role") == "student"
    ) or "(nothing yet)"
    release_connection(db)
    hint = ""
    try:
        raw = await _ask_llm(
            HINT_PROMPT.format(
                misconception=session.misconception[:300],
                question=session.question_prompt[:500],
                answer=session.question_correct_answer[:200],
                teaching=teaching[:1500],
                level=level,
            ),
            max_tokens=200,
            temperature=0.4,
        )
        hint = str((_extract_json(raw) or {}).get("hint") or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hint generation failed: %s", exc)
    if len(hint) < 15 or _gives_answer_away(hint, session.question_correct_answer):
        hint = FALLBACK_HINTS[level - 1]

    _append_turn(session, "hint", hint[:400])
    db.commit()
    db.refresh(session)
    return {"hint": hint[:400], "level": level, "hints_left": MAX_HINTS - level}


def study_lessons(db, session, limit: int = 2) -> list[dict[str, Any]]:
    """Lessons that teach this topic, so the student can learn before teaching."""
    from app.models.course import Course, Lesson

    try:
        rows = (
            db.query(Lesson, Course)
            .join(Course, Course.id == Lesson.course_id)
            .order_by(Lesson.order_index)
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not look up study lessons: %s", exc)
        return []
    found = []
    for lesson, course in rows:
        if session.topic_tag in (lesson.topic_tags or []):
            found.append({
                "id": str(lesson.id),
                "title": lesson.title,
                "course_title": course.title,
                "minutes": lesson.estimated_minutes,
            })
        if len(found) >= limit:
            break
    return found
