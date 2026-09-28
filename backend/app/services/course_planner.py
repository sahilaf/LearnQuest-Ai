"""AI course generation. OWNER: Member 1. See plan.md 6.4a.

A short course written for one learner from a stated goal: an outline call, then
one call per lesson, persisted as ordinary `courses` and `lessons` rows.

Why this runs as a job
----------------------
Measured 2026-09-27: ~8s per lesson-sized completion. A five-lesson course is
six calls and roughly 50-100s, against a 30s client timeout. So the endpoint
creates a `generation_jobs` row, returns its id, and this runs behind it while
the client polls.

What it does not do
-------------------
Nothing here checks whether the content is *true*. The model writes the lesson,
a later call writes a quiz from that lesson, grades it, and names the
misconception behind a wrong answer - four steps with no human anywhere. A
confidently wrong lesson therefore produces a confidently wrong diagnosis about
a belief the learner never held. Generated courses are marked
`source="ai_generated"` and kept private to the person who asked for them for
exactly that reason; see the warning in CHECKLIST Slot 9C before letting anyone
outside the team near this.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("learnquest.courseplanner")

# Bounds the cost of one request. Each lesson is a separate LLM call, and the
# free tier is a per-day quota shared with every other AI feature.
MIN_LESSONS = 3
MAX_LESSONS = 6
DEFAULT_LESSONS = 4

MIN_LESSON_CHARS = 200
MAX_GOAL_CHARS = 400

DIFFICULTIES = ("beginner", "intermediate", "advanced")


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _strip_fences(raw: str) -> str:
    """Remove an outer ```markdown fence if the model wrapped the whole lesson.

    Inner fenced code blocks are left alone - they are the worked example.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text


def slugify(title: str) -> str:
    """A URL-safe slug with a short suffix.

    `courses.slug` is globally unique, and two learners asking for "Learn SQL"
    would otherwise collide. The suffix keeps the readable part readable.
    """
    base = re.sub(r"[^a-z0-9]+", "-", str(title or "course").lower()).strip("-")
    return f"{base[:60] or 'course'}-{uuid.uuid4().hex[:6]}"


def validate_outline(db, payload: Any, n_lessons: int) -> dict[str, Any] | None:
    """Return a usable outline, or None.

    A lesson keeps an existing tag, or a new one the model proposed *with a
    label* (registered through `topics.register`, which prefers any existing
    match). Anything else is dropped rather than kept with an invented tag: an
    untagged lesson cannot feed mastery, so it cannot feed the misconception
    engine, which is the whole reason the course exists.

    The vocabulary used to be closed, and the prompt told the model to pick
    "the closest" tag when nothing fitted - so a course on operating systems
    came back filed under DBMS. That is worse than no tag at all.
    """
    from app.services.topics import resolve_or_register

    if not isinstance(payload, dict):
        return None

    title = str(payload.get("title") or "").strip()
    if len(title) < 4:
        return None

    raw_lessons = payload.get("lessons")
    if not isinstance(raw_lessons, list):
        return None

    lessons: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_lessons:
        if len(lessons) >= n_lessons:
            break
        if not isinstance(item, dict):
            continue

        lesson_title = str(item.get("title") or "").strip()
        if len(lesson_title) < 4:
            continue
        key = re.sub(r"\W+", " ", lesson_title.lower()).strip()
        if key in seen:
            continue

        tag = resolve_or_register(
            db, item.get("topic_tag"), item.get("topic_label"), payload.get("subject")
        )
        if not tag:
            logger.info(
                "Dropped generated lesson %r: unknown topic tag %r",
                lesson_title,
                item.get("topic_tag"),
            )
            continue

        lessons.append(
            {
                "title": lesson_title[:255],
                "topic_tag": tag,
                "summary": str(item.get("summary") or "").strip()[:600],
            }
        )
        seen.add(key)

    if len(lessons) < MIN_LESSONS:
        logger.info("Outline kept only %d usable lesson(s)", len(lessons))
        return None

    difficulty = str(payload.get("difficulty") or "beginner").strip().lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "beginner"

    try:
        hours = max(1, min(20, int(payload.get("estimated_hours") or 1)))
    except (TypeError, ValueError):
        hours = 1

    return {
        "title": title[:255],
        "description": str(payload.get("description") or "").strip()[:2000] or None,
        "subject": str(payload.get("subject") or "").strip()[:100] or None,
        "difficulty": difficulty,
        "estimated_hours": hours,
        "lessons": lessons,
    }


async def plan_outline(db, goal: str, n_lessons: int) -> dict[str, Any] | None:
    """One call: a goal becomes a validated lesson plan."""
    from app.services.llm_client import get_llm
    from app.services.prompts import COURSE_OUTLINE_PROMPT, TOPIC_RULES
    from app.services.topics import prompt_block

    # An empty vocabulary is no longer fatal: the model proposes tags instead.
    vocabulary = prompt_block(db) or "(none yet)"

    prompt = COURSE_OUTLINE_PROMPT.format(
        goal=str(goal or "").strip()[:MAX_GOAL_CHARS],
        topic_rules=TOPIC_RULES,
        topic_vocabulary=vocabulary,
        n_lessons=n_lessons,
    )

    try:
        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1600,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Course outline call failed: %s", exc)
        return None

    return validate_outline(db, _extract_json(raw), n_lessons)


async def write_lesson(
    *,
    course_title: str,
    difficulty: str,
    lesson: dict[str, Any],
    position: int,
    total: int,
    prior_titles: list[str],
) -> str:
    """Write one lesson's markdown.

    Falls back to the outline summary rather than raising. One failed call
    should cost the learner a thin lesson, not the whole course they waited a
    minute for - and the summary is still on-topic and correctly tagged.
    """
    from app.services.llm_client import get_llm
    from app.services.prompts import LESSON_CONTENT_PROMPT

    prior_context = ""
    if prior_titles:
        prior_context = (
            "Earlier lessons in this course, which the reader has already seen:\n"
            + "\n".join(f"- {t}" for t in prior_titles)
            + "\nDo not repeat them; build on them.\n"
        )

    prompt = LESSON_CONTENT_PROMPT.format(
        difficulty=difficulty,
        course_title=course_title,
        position=position,
        total=total,
        lesson_title=lesson["title"],
        summary=lesson["summary"] or lesson["title"],
        prior_context=prior_context,
    )

    try:
        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=2000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Lesson call failed for %r: %s", lesson["title"], exc)
        raw = ""

    content = _strip_fences(raw)
    if len(content) < MIN_LESSON_CHARS:
        logger.info("Lesson %r came back too thin; using its summary", lesson["title"])
        return (lesson["summary"] or lesson["title"]).strip()
    return content


def persist_course(db, *, user_id, outline: dict[str, Any], lesson_bodies: list[str]):
    """Write the course, its lessons and the learner's enrolment.

    Auto-published but private to the person who asked for it, and marked
    `source="ai_generated"` so it is never mistaken for reviewed material.
    """
    from app.models.course import Course, Enrollment, Lesson

    course = Course(
        id=uuid.uuid4(),
        title=outline["title"],
        slug=slugify(outline["title"]),
        description=outline["description"],
        subject=outline["subject"],
        difficulty=outline["difficulty"],
        estimated_hours=outline["estimated_hours"],
        is_published=True,
        source="ai_generated",
        is_private=True,
        created_by=user_id,
    )
    db.add(course)
    db.flush()

    for index, (item, body) in enumerate(zip(outline["lessons"], lesson_bodies)):
        db.add(
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                title=item["title"],
                order_index=index,
                content_md=body,
                estimated_minutes=10,
                topic_tags=[item["topic_tag"]],
            )
        )

    # Enrol them, or the course they just asked for does not appear anywhere
    # they would think to look.
    db.add(
        Enrollment(
            id=uuid.uuid4(),
            user_id=user_id,
            course_id=course.id,
            enrolled_at=_now(),
        )
    )

    db.commit()
    db.refresh(course)
    return course


async def generate_course(
    db,
    *,
    user_id,
    goal: str,
    n_lessons: int = DEFAULT_LESSONS,
    job_id=None,
) -> dict[str, Any]:
    """Goal -> outline -> lessons -> a course the learner is enrolled in.

    Reports coarse progress as it goes; the client watches a bar for about a
    minute and "lesson 3 of 4" is all it needs.
    """
    from app.services.events import emit
    from app.services.jobs import set_progress

    goal = str(goal or "").strip()
    if len(goal) < 4:
        raise ValueError("Tell us what you want to learn.")

    n_lessons = max(MIN_LESSONS, min(MAX_LESSONS, int(n_lessons or DEFAULT_LESSONS)))

    if job_id:
        set_progress(db, job_id, 5)

    outline = await plan_outline(db, goal, n_lessons)
    if outline is None:
        raise RuntimeError(
            "Could not plan a course for that goal. Try describing it differently."
        )

    total = len(outline["lessons"])
    if job_id:
        set_progress(db, job_id, 15)

    bodies: list[str] = []
    prior_titles: list[str] = []
    for index, lesson in enumerate(outline["lessons"]):
        body = await write_lesson(
            course_title=outline["title"],
            difficulty=outline["difficulty"],
            lesson=lesson,
            position=index + 1,
            total=total,
            prior_titles=list(prior_titles),
        )
        bodies.append(body)
        prior_titles.append(lesson["title"])
        if job_id:
            set_progress(db, job_id, 15 + int(80 * (index + 1) / total))

    course = persist_course(db, user_id=user_id, outline=outline, lesson_bodies=bodies)
    topics = sorted({item["topic_tag"] for item in outline["lessons"]})

    try:
        emit(
            db=db,
            user_id=user_id,
            event_type="course.generated",
            payload={
                "course_id": str(course.id),
                "slug": course.slug,
                "lessons": total,
                "topics": topics,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not emit course.generated: %s", exc)

    logger.info("Generated course %r (%d lessons) for %s", course.title, total, user_id)
    return {
        "course_id": str(course.id),
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "difficulty": course.difficulty,
        "lessons": total,
        "topics": topics,
    }
