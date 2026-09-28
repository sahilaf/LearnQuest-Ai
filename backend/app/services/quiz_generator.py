"""AI quiz generation. OWNER: Member 1. See plan.md 6.4.

A quiz written for one student, fresh every time. Two things make it personal:

  difficulty  drawn from `topic_mastery`, so a learner at 0.2 on a topic is not
              handed the same questions as one at 0.9.
  targeting   if an active misconception exists for the topic, the questions are
              aimed at it. That closes the loop: the belief the app named is the
              belief it re-tests, instead of sampling the topic at random and
              hoping the same gap comes up again.

Design notes
------------
Tags are resolved against the `topics` vocabulary and never taken from the
model's reply verbatim. A question tagged with something invented is worse than
no question: it writes a mastery row nothing else will ever join to, and the
misconception recorded against it disappears from the map.

Nothing here raises on a bad reply. A malformed question is dropped and the rest
are kept, because returning four good questions beats a 500, and a model that
returns one unusable item on a five-item request is normal.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger("learnquest.quizgen")

MAX_QUESTIONS = 10
DEFAULT_QUESTIONS = 5
ALLOWED_TYPES = ("mcq", "true_false", "short_answer")

# Mastery thresholds (plan.md 6.4).
EASY_BELOW = 0.4
HARD_ABOVE = 0.75

TRUE_FALSE_OPTIONS = ["True", "False"]

MISCONCEPTION_HINT = """
This learner currently believes something false about this topic:

  "{misconception}"

Write at least one question that this belief would cause them to answer wrongly,
so the belief is actually tested rather than avoided. Make the wrong option that
the belief leads to a plausible distractor, not an obviously silly one. Do not
mention the belief in the question text.

Only do this if the lesson above actually teaches the idea this belief is
about. If it does not, ignore this note completely - a question the lesson
cannot answer is worse than one that misses the belief.
"""


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


def difficulty_for(mastery: float | None) -> str:
    """Mastery score -> the difficulty this learner should be working at."""
    if mastery is None:
        return "medium"
    if mastery < EASY_BELOW:
        return "easy"
    if mastery > HARD_ABOVE:
        return "hard"
    return "medium"


def _mastery_row(db, user_id, topic_tag: str):
    from app.models.ai import TopicMastery

    try:
        return (
            db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == user_id,
                TopicMastery.topic_tag == topic_tag,
            )
            .first()
        )
    except Exception:  # noqa: BLE001
        return None


def validate_questions(
    db,
    raw_questions: Any,
    allowed_tags: list[str],
    types: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    """Keep only questions that are actually usable.

    Every rule here exists because breaking it produces a quiz that looks fine
    and grades wrongly: an mcq whose correct_answer is not among its options can
    never be answered correctly, and a duplicated prompt lets one mistake cost
    two marks.
    """
    from app.services.topics import resolve

    if not isinstance(raw_questions, list):
        return []

    out: list[dict[str, Any]] = []
    seen_prompts: set[str] = set()

    for item in raw_questions:
        if len(out) >= limit:
            break
        if not isinstance(item, dict):
            continue

        prompt = str(item.get("prompt") or "").strip()
        if len(prompt) < 10:
            continue
        key = re.sub(r"\W+", " ", prompt.lower()).strip()
        if key in seen_prompts:
            continue

        qtype = str(item.get("type") or "mcq").strip().lower()
        if qtype not in types or qtype not in ALLOWED_TYPES:
            continue

        correct = str(item.get("correct_answer") or "").strip()
        if not correct:
            continue

        options = item.get("options")
        if qtype == "mcq":
            if not isinstance(options, list) or len(options) < 2:
                continue
            options = [str(o).strip() for o in options if str(o).strip()]
            if len(set(options)) < 2:
                continue
            # The answer has to be one of the choices, or the question is
            # unanswerable no matter what the student knows.
            if correct not in options:
                match = next((o for o in options if o.lower() == correct.lower()), None)
                if match is None:
                    continue
                correct = match
        elif qtype == "true_false":
            normalised = correct.strip().lower()
            if normalised not in ("true", "false"):
                continue
            correct = "True" if normalised == "true" else "False"
            options = list(TRUE_FALSE_OPTIONS)
        else:
            options = None

        # A tag the vocabulary does not know is dropped, and a question left
        # with no usable tag goes with it: an untagged question cannot feed
        # mastery, so it cannot feed the misconception engine either.
        tags = resolve(db, [item.get("topic_tag")]) if item.get("topic_tag") else []
        if not tags:
            tags = allowed_tags[:1]
        if not tags:
            continue

        out.append(
            {
                "type": qtype,
                "prompt": prompt[:1000],
                "options": options,
                "correct_answer": correct[:500],
                "explanation": str(item.get("explanation") or "").strip()[:1000] or None,
                "topic_tag": tags[0],
                "difficulty": str(item.get("difficulty") or "medium").strip().lower(),
            }
        )
        seen_prompts.add(key)

    return out


async def generate_questions(
    db,
    *,
    lesson_content: str,
    lesson_title: str,
    allowed_tags: list[str],
    num_questions: int,
    difficulty: str,
    types: tuple[str, ...],
    misconception: str | None = None,
) -> list[dict[str, Any]]:
    """One LLM round trip, validated. Returns [] rather than raising."""
    from app.services.llm_client import get_llm
    from app.services.prompts import QUIZ_GENERATION_PROMPT

    prompt = QUIZ_GENERATION_PROMPT.format(
        n=num_questions,
        difficulty=difficulty,
        types=", ".join(types),
        topic_tags=", ".join(allowed_tags),
        lesson_content=(lesson_content or lesson_title)[:6000],
    )
    if misconception:
        prompt += MISCONCEPTION_HINT.format(misconception=misconception[:300])

    try:
        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.7,  # some spread, or every regeneration repeats itself
            max_tokens=2000,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Quiz generation call failed: %s", exc)
        return []

    payload = _extract_json(raw) or {}
    return validate_questions(
        db, payload.get("questions"), allowed_tags, types, num_questions
    )


def persist_quiz(
    db,
    *,
    user_id,
    questions: list[dict[str, Any]],
    title: str,
    lesson_id=None,
    course_id=None,
    topic_tags: list[str] | None = None,
):
    """Write the quiz in M2's shape, so every existing endpoint just works.

    Generated quizzes are ordinary rows marked `source="ai_generated"`. Nothing
    downstream - starting an attempt, grading it, the misconception engine -
    needs to know where the questions came from, and that is the point.
    """
    from app.models.quiz import Question, Quiz

    quiz = Quiz(
        id=uuid.uuid4(),
        lesson_id=lesson_id,
        course_id=course_id,
        title=title[:255],
        source="ai_generated",
        difficulty=questions[0]["difficulty"] if questions else "medium",
        generated_by_user=user_id,
        topic_tags=topic_tags or sorted({q["topic_tag"] for q in questions}),
    )
    db.add(quiz)
    db.flush()

    for index, item in enumerate(questions):
        db.add(
            Question(
                id=uuid.uuid4(),
                quiz_id=quiz.id,
                type=item["type"],
                prompt=item["prompt"],
                options=item["options"],
                correct_answer=item["correct_answer"],
                explanation=item["explanation"],
                topic_tag=item["topic_tag"],
                difficulty=item["difficulty"],
                order_index=index,
            )
        )

    db.commit()
    db.refresh(quiz)
    return quiz


async def generate_quiz(
    db,
    *,
    lesson_id,
    user_id,
    num_questions: int = DEFAULT_QUESTIONS,
    difficulty: str = "auto",
    types: tuple[str, ...] = ("mcq", "true_false"),
):
    """Generate, validate and persist a quiz for one lesson.

    Returns M2's quiz shape with answers stripped, exactly as
    `GET /api/quizzes/{id}` would - the caller is about to take this quiz, so it
    must not be handed the answers on the way in.
    """
    from app.models.course import Lesson
    from app.services.events import emit
    from app.services.mastery import misconception_status
    from app.services.topics import active_tags, resolve

    num_questions = max(1, min(MAX_QUESTIONS, int(num_questions or DEFAULT_QUESTIONS)))
    types = tuple(t for t in types if t in ALLOWED_TYPES) or ("mcq",)

    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if lesson is None:
        raise ValueError("Lesson not found.")

    allowed_tags = resolve(db, lesson.topic_tags or []) or active_tags(db)[:1]
    if not allowed_tags:
        raise ValueError("No topic vocabulary is configured.")

    primary_tag = allowed_tags[0]
    row = _mastery_row(db, user_id, primary_tag)

    if difficulty == "auto":
        difficulty = difficulty_for(float(row.mastery_score) if row else None)

    # Aim at the belief the app already named, rather than sampling the topic
    # again and hoping the same gap resurfaces.
    misconception = None
    if row is not None and row.misconception:
        if misconception_status(row) in ("active", "fading"):
            misconception = row.misconception

    questions = await generate_questions(
        db,
        lesson_content=lesson.content_md or "",
        lesson_title=lesson.title,
        allowed_tags=allowed_tags,
        num_questions=num_questions,
        difficulty=difficulty,
        types=types,
        misconception=misconception,
    )
    if not questions:
        raise RuntimeError("The AI did not return any usable questions.")

    quiz = persist_quiz(
        db,
        user_id=user_id,
        questions=questions,
        title=f"{lesson.title} - practice",
        lesson_id=lesson.id,
        course_id=lesson.course_id,
        topic_tags=allowed_tags,
    )

    try:
        emit(
            db=db,
            user_id=user_id,
            event_type="quiz.generated",
            payload={
                "quiz_id": str(quiz.id),
                "lesson_id": str(lesson.id),
                "topic": primary_tag,
                "difficulty": difficulty,
                "targeted_misconception": bool(misconception),
            },
        )
    except Exception as exc:  # noqa: BLE001 - never fail a quiz over telemetry
        logger.warning("Could not emit quiz.generated: %s", exc)

    return quiz.to_dict(include_questions=True, strip_answers=True)


async def generate_adaptive_quiz(
    db,
    *,
    user_id,
    num_questions: int = DEFAULT_QUESTIONS,
    types: tuple[str, ...] = ("mcq", "true_false"),
):
    """A quiz across this learner's weakest topics, ignoring lesson scope.

    Picks the lowest-mastery topics first and, where one carries a live
    misconception, targets it. A learner with no history yet gets the first
    topics in the vocabulary at medium difficulty rather than an error.
    """
    from app.models.ai import TopicMastery
    from app.models.course import Lesson
    from app.services.events import emit
    from app.services.mastery import misconception_status
    from app.services.topics import active_tags

    num_questions = max(1, min(MAX_QUESTIONS, int(num_questions or DEFAULT_QUESTIONS)))
    types = tuple(t for t in types if t in ALLOWED_TYPES) or ("mcq",)

    known = set(active_tags(db))
    if not known:
        raise ValueError("No topic vocabulary is configured.")

    weak = (
        db.query(TopicMastery)
        .filter(TopicMastery.user_id == user_id, TopicMastery.topic_tag.in_(known))
        .order_by(TopicMastery.mastery_score.asc())
        .limit(3)
        .all()
    )

    if weak:
        tags = [r.topic_tag for r in weak]
        mastery = min(float(r.mastery_score or 0.5) for r in weak)
        live = [
            r.misconception
            for r in weak
            if r.misconception and misconception_status(r) in ("active", "fading")
        ]
        misconception = live[0] if live else None
    else:
        tags = active_tags(db)[:3]
        mastery = None
        misconception = None

    difficulty = difficulty_for(mastery)

    # Ground the questions in whatever real lesson content covers these topics.
    # Generating from the tag alone produces plausible but unmoored questions.
    lessons = (
        db.query(Lesson)
        .filter(Lesson.topic_tags.isnot(None))
        .order_by(Lesson.order_index)
        .limit(40)
        .all()
    )
    relevant = [
        f"## {lesson.title}\n{(lesson.content_md or '')[:1200]}"
        for lesson in lessons
        if set(lesson.topic_tags or []) & set(tags)
    ][:4]

    questions = await generate_questions(
        db,
        lesson_content="\n\n".join(relevant),
        lesson_title="Review: " + ", ".join(tags),
        allowed_tags=tags,
        num_questions=num_questions,
        difficulty=difficulty,
        types=types,
        misconception=misconception,
    )
    if not questions:
        raise RuntimeError("The AI did not return any usable questions.")

    quiz = persist_quiz(
        db,
        user_id=user_id,
        questions=questions,
        title="Your practice set",
        topic_tags=tags,
    )

    try:
        emit(
            db=db,
            user_id=user_id,
            event_type="quiz.generated",
            payload={
                "quiz_id": str(quiz.id),
                "topics": tags,
                "difficulty": difficulty,
                "adaptive": True,
                "targeted_misconception": bool(misconception),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not emit quiz.generated: %s", exc)

    return quiz.to_dict(include_questions=True, strip_answers=True)
