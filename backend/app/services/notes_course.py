"""Uploaded notes -> a course that teaches them. OWNER: Member 1.

M3's `notes_extractor` gets the text out of the file. This turns that text into
lessons someone can learn from.

What it replaced
----------------
The first version split the text on headings or every ~1800 characters and saved
each piece as a lesson, word for word, then tagged it by keyword overlap with
the topic list - falling back to the *first topic on the list* when nothing
matched. Measured 2026-09-29 on a real upload of operating-systems slides:

  - lessons titled "Dept. of CSE, BUET" and "Any examinee found adopting un..."
    because the first line of each chunk was a page header;
  - the lesson body was the slide text, unexplained;
  - every lesson tagged `dbms.er_model`, so "Practice this lesson" asked the
    quiz generator for DBMS questions - and aimed them at the DBMS
    misconception the student already had on record.

How it works now
----------------
1. Chunk the text (~1500 chars, on line boundaries) and number the chunks.
2. One outline call: the model reads the numbered notes and returns lessons,
   each naming the chunks it is taught from and a topic - existing, or a new
   one proposed with a label and registered through `topics.register`.
3. One call per lesson, given *only its own chunks*, so the lesson teaches the
   student's material rather than the model's general idea of the subject.
4. Persist as a private `source="uploaded"` course, enrol, seed review items.

It runs as a generation job: a six-lesson course is seven model calls, well
past the client's 30-second timeout.

Nothing here checks that the model's explanations are correct - the same
caveat as `course_planner`. Keeping each lesson grounded in the student's own
notes narrows that risk; it does not remove it.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("learnquest.notescourse")

CHUNK_CHARS = 1500
MAX_SOURCE_CHARS = 40_000  # what the outline call sees; ~10k tokens
MAX_LESSON_SOURCE_CHARS = 8_000

MIN_LESSONS = 2
MAX_LESSONS = 8
MIN_LESSON_CHARS = 200

DIFFICULTIES = ("beginner", "intermediate", "advanced")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #


def chunk_notes(text: str, size: int = CHUNK_CHARS, limit: int = MAX_SOURCE_CHARS) -> list[str]:
    """Split notes into roughly `size`-character chunks on line boundaries.

    PDF extraction yields single newlines far more often than paragraphs, so
    this works on lines. A single line longer than `size` is cut hard rather
    than becoming one enormous chunk. Text past `limit` is dropped and logged:
    the outline call has to see every chunk it may assign.
    """
    text = (text or "").strip()
    if len(text) > limit:
        logger.info("Notes truncated from %d to %d chars", len(text), limit)
        text = text[:limit]

    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in text.splitlines():
        line = line.rstrip()
        while len(line) > size:
            if current:
                chunks.append("\n".join(current).strip())
                current, length = [], 0
            chunks.append(line[:size])
            line = line[size:]
        current.append(line)
        length += len(line) + 1
        if length >= size:
            chunks.append("\n".join(current).strip())
            current, length = [], 0
    if current and "\n".join(current).strip():
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


def _numbered(chunks: list[str]) -> str:
    return "\n\n".join(f"[[{i}]]\n{c}" for i, c in enumerate(chunks, 1))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())}


def _best_chunks(chunks: list[str], title: str, summary: str, k: int = 2) -> list[int]:
    """Fallback when the model names no chunks: the ones sharing most words."""
    wanted = _words(f"{title} {summary}")
    scored = sorted(
        range(len(chunks)),
        key=lambda i: len(wanted & _words(chunks[i])),
        reverse=True,
    )
    return sorted(i + 1 for i in scored[:k])


# --------------------------------------------------------------------------- #
# Outline
# --------------------------------------------------------------------------- #


def validate_outline(db, payload: Any, chunks: list[str]) -> dict[str, Any] | None:
    """A usable outline, or None.

    Same tagging rule as `course_planner.validate_outline`: an existing tag, or
    a labelled proposal registered through the vocabulary, or the lesson goes.
    """
    from app.services.topics import resolve_or_register

    if not isinstance(payload, dict):
        return None
    raw_lessons = payload.get("lessons")
    if not isinstance(raw_lessons, list):
        return None

    subject = str(payload.get("subject") or "").strip()[:100] or None
    lessons: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_lessons:
        if len(lessons) >= MAX_LESSONS:
            break
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        key = re.sub(r"\W+", " ", title.lower()).strip()
        if len(title) < 4 or key in seen:
            continue

        tag = resolve_or_register(db, item.get("topic_tag"), item.get("topic_label"), subject)
        if not tag:
            logger.info("Dropped notes lesson %r: no usable topic", title)
            continue

        summary = str(item.get("summary") or "").strip()[:600]
        picked: list[int] = []
        for n in item.get("chunks") or []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(chunks) and n not in picked:
                picked.append(n)
        if not picked:
            picked = _best_chunks(chunks, title, summary)

        lessons.append(
            {"title": title[:255], "summary": summary, "topic_tag": tag, "chunks": sorted(picked)}
        )
        seen.add(key)

    if len(lessons) < MIN_LESSONS:
        logger.info("Notes outline kept only %d usable lesson(s)", len(lessons))
        return None

    difficulty = str(payload.get("difficulty") or "intermediate").strip().lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "intermediate"

    return {
        "title": str(payload.get("title") or "").strip()[:255] or None,
        "description": str(payload.get("description") or "").strip()[:2000] or None,
        "subject": subject,
        "difficulty": difficulty,
        "lessons": lessons,
    }


async def plan_outline(db, chunks: list[str]) -> dict[str, Any] | None:
    from app.services.course_planner import _extract_json
    from app.services.llm_client import get_llm
    from app.services.prompts import NOTES_OUTLINE_PROMPT, TOPIC_RULES
    from app.services.topics import prompt_block

    prompt = NOTES_OUTLINE_PROMPT.format(
        min_lessons=MIN_LESSONS,
        max_lessons=min(MAX_LESSONS, max(MIN_LESSONS, len(chunks))),
        topic_rules=TOPIC_RULES,
        topic_vocabulary=prompt_block(db) or "(none yet)",
        notes=_numbered(chunks),
    )
    try:
        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2500,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notes outline call failed: %s", exc)
        raise RuntimeError(f"outline call failed: {exc}") from exc

    return validate_outline(db, _extract_json(raw), chunks)


# --------------------------------------------------------------------------- #
# Lessons
# --------------------------------------------------------------------------- #


def _source_for(chunks: list[str], numbers: list[int]) -> str:
    text = "\n\n".join(chunks[n - 1] for n in numbers)
    return text[:MAX_LESSON_SOURCE_CHARS]


def _fallback_body(lesson: dict[str, Any], source: str) -> str:
    """What a lesson says when its call failed: honest, on-topic, still tagged."""
    return (
        f"{lesson['summary'] or lesson['title']}\n\n"
        "> This lesson could not be written up by the AI just now, so it shows "
        "the part of your notes it covers. Ask the tutor to explain any of it.\n\n"
        f"### From your notes\n\n{source}"
    )


async def write_lesson(
    *,
    course_title: str,
    difficulty: str,
    lesson: dict[str, Any],
    source: str,
    position: int,
    total: int,
    prior_titles: list[str],
) -> str:
    from app.services.course_planner import _strip_fences
    from app.services.llm_client import get_llm
    from app.services.prompts import NOTES_LESSON_PROMPT

    prior_context = ""
    if prior_titles:
        prior_context = (
            "Earlier lessons in this course, which the reader has already seen:\n"
            + "\n".join(f"- {t}" for t in prior_titles)
            + "\nDo not repeat them; build on them.\n"
        )

    prompt = NOTES_LESSON_PROMPT.format(
        difficulty=difficulty,
        course_title=course_title,
        position=position,
        total=total,
        lesson_title=lesson["title"],
        summary=lesson["summary"] or lesson["title"],
        prior_context=prior_context,
        source=source,
    )
    try:
        raw = await get_llm().complete(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2200,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notes lesson call failed for %r: %s", lesson["title"], exc)
        raw = ""

    content = _strip_fences(raw)
    if len(content) < MIN_LESSON_CHARS:
        return _fallback_body(lesson, source)
    return content


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def _minutes(body: str) -> int:
    return max(3, min(30, round(len(body.split()) / 150)))


def persist_course(
    db,
    *,
    user_id,
    filename: str,
    title: str,
    outline: dict[str, Any],
    bodies: list[str],
) -> tuple[Any, list[Any]]:
    from app.models.ai import ReviewItem
    from app.models.course import Course, Enrollment, Lesson
    from app.services.course_planner import slugify

    minutes = [_minutes(b) for b in bodies]
    course = Course(
        id=uuid.uuid4(),
        title=title[:255],
        slug=f"upload-{slugify(title)}",
        description=outline["description"] or f"A course built from your notes ({filename}).",
        subject=(outline["subject"] or "Uploaded Notes")[:100],
        difficulty=outline["difficulty"],
        estimated_hours=max(1, round(sum(minutes) / 60)),
        is_published=True,
        source="uploaded",
        is_private=True,
        created_by=user_id,
        created_at=_now(),
    )
    db.add(course)
    db.flush()

    lessons = []
    first_lesson_for: dict[str, uuid.UUID] = {}
    for index, (item, body) in enumerate(zip(outline["lessons"], bodies)):
        lesson = Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            title=item["title"],
            order_index=index,
            content_md=body,
            estimated_minutes=minutes[index],
            topic_tags=[item["topic_tag"]],
            created_at=_now(),
        )
        db.add(lesson)
        lessons.append(lesson)
        first_lesson_for.setdefault(item["topic_tag"], lesson.id)

    db.add(Enrollment(id=uuid.uuid4(), user_id=user_id, course_id=course.id, enrolled_at=_now()))

    # Seed the review queue (plan.md 6.13): each topic comes back tomorrow.
    due = _now() + timedelta(days=1)
    for tag, lesson_id in first_lesson_for.items():
        exists = (
            db.query(ReviewItem)
            .filter(ReviewItem.user_id == user_id, ReviewItem.topic_tag == tag)
            .first()
        )
        if not exists:
            db.add(
                ReviewItem(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    topic_tag=tag,
                    source_lesson_id=lesson_id,
                    due_at=due,
                    interval_days=1,
                    streak=0,
                )
            )

    db.commit()
    db.refresh(course)
    return course, lessons


async def build_course_from_notes(
    db,
    *,
    user_id,
    text: str,
    filename: str,
    custom_title: str | None = None,
    job_id=None,
) -> dict[str, Any]:
    """Extracted text -> outline -> grounded lessons -> an enrolled course."""
    from app.services.events import emit
    from app.services.jobs import set_progress

    chunks = chunk_notes(text)
    if not chunks:
        raise ValueError("These notes have no readable text.")

    if job_id:
        set_progress(db, job_id, 5)

    outline = await plan_outline(db, chunks)
    if outline is None:
        raise RuntimeError(
            "Could not find enough study material in these notes to build a course."
        )
    if job_id:
        set_progress(db, job_id, 20)

    title = (custom_title or "").strip() or outline["title"] or re.sub(
        r"\.[^.]+$", "", filename
    ).replace("_", " ").strip().title() or "My notes"

    total = len(outline["lessons"])
    bodies: list[str] = []
    prior: list[str] = []
    for index, lesson in enumerate(outline["lessons"]):
        body = await write_lesson(
            course_title=title,
            difficulty=outline["difficulty"],
            lesson=lesson,
            source=_source_for(chunks, lesson["chunks"]),
            position=index + 1,
            total=total,
            prior_titles=list(prior),
        )
        bodies.append(body)
        prior.append(lesson["title"])
        if job_id:
            set_progress(db, job_id, 20 + int(75 * (index + 1) / total))

    course, lessons = persist_course(
        db, user_id=user_id, filename=filename, title=title, outline=outline, bodies=bodies
    )
    topics = sorted({item["topic_tag"] for item in outline["lessons"]})

    for event_type, payload in (
        ("course.enrolled", {"course_id": str(course.id)}),
        (
            "course.generated",
            {"course_id": str(course.id), "slug": course.slug, "lessons": total, "topics": topics},
        ),
    ):
        try:
            emit(db, user_id, event_type, payload)
        except Exception as exc:  # noqa: BLE001 - never fail a course over telemetry
            logger.warning("Could not emit %s: %s", event_type, exc)

    logger.info("Built course %r (%d lessons) from %s for %s", title, total, filename, user_id)

    # The upload page renders this directly. Lesson bodies are left out: they
    # are fetched when opened, and a job result is not the place for 30KB.
    return {
        "course_id": str(course.id),
        "slug": course.slug,
        "title": course.title,
        "course": course.to_dict(),
        "lessons": [
            {
                "id": str(l.id),
                "title": l.title,
                "order_index": l.order_index,
                "estimated_minutes": l.estimated_minutes,
                "topic_tags": l.topic_tags or [],
            }
            for l in lessons
        ],
        "topics": topics,
    }
