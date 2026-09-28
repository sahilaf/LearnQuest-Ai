"""Document extraction and notes-to-course pipeline.

OWNER: Member 3. See plan.md §6.13, §8.6, and CHECKLIST.md Slot 11.

Turns uploaded PDF, Markdown, or text notes into a private course with lessons,
topics from M1's controlled vocabulary, and review items seeded for spaced repetition.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ai import ReviewItem
from app.models.course import Course, Enrollment, Lesson
from app.services.events import emit
from app.services.topics import active_tags, resolve, vocabulary

logger = logging.getLogger("learnquest.upload")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
MIN_TEXT_CHARS = 50
MIN_LESSONS = 2
MAX_LESSONS = 8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s[:60] or "notes"


def validate_file(filename: str, content: bytes, content_type: str | None = None) -> None:
    """Validate file size and extension to prevent malicious uploads or OOM."""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty.",
            headers={"X-Error-Code": "UPLOAD_EMPTY_FILENAME"},
        )

    # Validate file extension
    lower_name = filename.lower()
    has_valid_ext = any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS)
    if not has_valid_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a PDF (.pdf), Markdown (.md), or text (.txt) file.",
            headers={"X-Error-Code": "UPLOAD_UNSUPPORTED_TYPE"},
        )

    # Check file size limit (10MB)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            headers={"X-Error-Code": "UPLOAD_TOO_LARGE"},
        )

    if len(content) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty or corrupted.",
            headers={"X-Error-Code": "UPLOAD_EMPTY_FILE"},
        )


def extract_text_from_file(filename: str, content: bytes, content_type: str | None = None) -> str:
    """Extract plain text / markdown from PDF or text-based files."""
    validate_file(filename, content, content_type)
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Encrypted or password-protected PDF files are not supported.",
                    headers={"X-Error-Code": "UPLOAD_PDF_ENCRYPTED"},
                )

            pages_text = []
            for idx, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    pages_text.append(extracted.strip())

            full_text = "\n\n".join(pages_text).strip()
            if len(full_text) < MIN_TEXT_CHARS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not extract readable text from PDF. The document may be scanned, image-only, or empty.",
                    headers={"X-Error-Code": "UPLOAD_PDF_SCANNED_OR_EMPTY"},
                )
            return full_text
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read PDF document: {exc}",
                headers={"X-Error-Code": "UPLOAD_PDF_READ_ERROR"},
            ) from exc

    # Plain text / Markdown
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not decode text file with UTF-8 or Latin-1 encoding.",
                headers={"X-Error-Code": "UPLOAD_DECODE_ERROR"},
            ) from exc

    clean_text = text.strip()
    if len(clean_text) < MIN_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file contains insufficient text to create a course.",
            headers={"X-Error-Code": "UPLOAD_INSUFFICIENT_TEXT"},
        )
    return clean_text


def split_into_lessons(text: str, default_course_title: str) -> list[dict[str, Any]]:
    """Split extracted text into structured lesson-sized sections.

    Strategy:
    1. Look for Markdown headings (# Heading, ## Heading).
    2. Look for explicit Chapter/Section/Lesson regex patterns.
    3. Fallback to paragraph-based chunking (~1500-2500 chars).
    """
    lines = text.splitlines()

    # 1. Try Markdown headings
    heading_indices = []
    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
        if match:
            heading_indices.append((i, match.group(2).strip()))

    sections: list[dict[str, Any]] = []

    if len(heading_indices) >= MIN_LESSONS:
        for idx, (line_idx, heading_title) in enumerate(heading_indices):
            start = line_idx + 1
            end = heading_indices[idx + 1][0] if idx + 1 < len(heading_indices) else len(lines)
            body = "\n".join(lines[start:end]).strip()
            if len(body) >= 60:
                clean_title = re.sub(r"^[0-9\.\-\:\s]+", "", heading_title).strip() or heading_title
                sections.append({
                    "title": clean_title[:200],
                    "content_md": f"## {clean_title}\n\n{body}",
                })

    # 2. Try Chapter / Section patterns if Markdown headings weren't enough
    if len(sections) < MIN_LESSONS:
        sections = []
        chap_indices = []
        for i, line in enumerate(lines):
            match = re.match(r"^(Chapter|Section|Module|Part|Unit|Lesson)\s+(\d+|[A-ZIVXLC]+)[:\.\-\s]+(.*)$", line.strip(), re.I)
            if match:
                marker_title = match.group(0).strip()
                chap_indices.append((i, marker_title))

        if len(chap_indices) >= MIN_LESSONS:
            for idx, (line_idx, chap_title) in enumerate(chap_indices):
                start = line_idx + 1
                end = chap_indices[idx + 1][0] if idx + 1 < len(chap_indices) else len(lines)
                body = "\n".join(lines[start:end]).strip()
                if len(body) >= 60:
                    sections.append({
                        "title": chap_title[:200],
                        "content_md": f"## {chap_title}\n\n{body}",
                    })

    # 3. Fallback: chunk paragraphs on logical boundaries
    if len(sections) < MIN_LESSONS:
        sections = []
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current_chunk: list[str] = []
        current_len = 0
        target_chunk_len = 1800

        for p in paragraphs:
            current_chunk.append(p)
            current_len += len(p)
            if current_len >= target_chunk_len:
                body = "\n\n".join(current_chunk).strip()
                first_line = current_chunk[0].splitlines()[0][:80].strip()
                first_line_clean = re.sub(r"[#*_]+", "", first_line).strip()
                title = first_line_clean if len(first_line_clean) >= 6 else f"Part {len(sections) + 1}"
                sections.append({
                    "title": title[:200],
                    "content_md": f"## {title}\n\n{body}",
                })
                current_chunk = []
                current_len = 0

        if current_chunk:
            body = "\n\n".join(current_chunk).strip()
            if sections and len(body) < 300:
                # Append remainder to last section
                sections[-1]["content_md"] += f"\n\n{body}"
            else:
                first_line = current_chunk[0].splitlines()[0][:80].strip()
                first_line_clean = re.sub(r"[#*_]+", "", first_line).strip()
                title = first_line_clean if len(first_line_clean) >= 6 else f"Part {len(sections) + 1}"
                sections.append({
                    "title": title[:200],
                    "content_md": f"## {title}\n\n{body}",
                })

    # If still only 1 section, split it into 2 parts
    if len(sections) == 1:
        single = sections[0]
        full_body = single["content_md"]
        mid = len(full_body) // 2
        split_idx = full_body.find("\n\n", mid)
        if split_idx == -1:
            split_idx = mid
        p1 = full_body[:split_idx].strip()
        p2 = full_body[split_idx:].strip()
        sections = [
            {"title": f"{single['title']} (Part 1)", "content_md": p1},
            {"title": f"{single['title']} (Part 2)", "content_md": p2},
        ]

    # Constrain to MAX_LESSONS (keep first N)
    sections = sections[:MAX_LESSONS]

    # Calculate estimated minutes for each lesson
    for idx, sec in enumerate(sections):
        words = len(sec["content_md"].split())
        sec["estimated_minutes"] = max(3, min(30, round(words / 150)))
        sec["order_index"] = idx

    return sections


def assign_topic_tags(db: Session, lessons: list[dict[str, Any]], course_title: str) -> None:
    """Assign topic tags from the controlled vocabulary (app.services.topics).

    CRITICAL RULE (plan.md §3.1, §8.3): A lesson CANNOT be saved without at least one topic_tag.
    """
    vocab = vocabulary(db)
    all_active = active_tags(db)

    if not all_active:
        # Emergency fallback if topics table is completely unseeded
        for l in lessons:
            l["topic_tags"] = ["general"]
        return

    # Prepare search terms for each topic
    topic_matchers = []
    for item in vocab:
        tag = item["tag"]
        label = item.get("label", "").lower()
        subject = item.get("subject", "").lower()
        # Words from tag and label
        tag_parts = set(re.findall(r"\w+", tag.lower()))
        label_parts = set(re.findall(r"\w+", label))
        topic_matchers.append((tag, tag_parts | label_parts, label))

    assigned_in_course: set[str] = set()

    for lesson in lessons:
        text_for_matching = (lesson["title"] + " " + lesson["content_md"] + " " + course_title).lower()
        lesson_words = set(re.findall(r"\w+", text_for_matching))

        matched_tags: list[str] = []
        for tag, keywords, label in topic_matchers:
            # Check for direct phrase match or multi-keyword intersection
            if tag.replace(".", " ") in text_for_matching or label in text_for_matching:
                matched_tags.append(tag)
            else:
                overlap = keywords & lesson_words
                # Substantial keyword overlap
                if len(overlap) >= 2 or (len(keywords) == 1 and len(overlap) == 1):
                    matched_tags.append(tag)

        # Resolve through M1's vocabulary checker
        resolved_tags = resolve(db, matched_tags)
        if resolved_tags:
            lesson["topic_tags"] = resolved_tags[:3]
            assigned_in_course.update(resolved_tags[:3])
        else:
            # Fallback to course-wide tag if already matched, or first active topic
            if assigned_in_course:
                lesson["topic_tags"] = [next(iter(assigned_in_course))]
            else:
                lesson["topic_tags"] = [all_active[0]]


def process_uploaded_notes(
    db: Session,
    user_id: uuid.UUID,
    filename: str,
    content: bytes,
    content_type: str | None = None,
    custom_title: str | None = None,
) -> dict[str, Any]:
    """End-to-end processing: extract -> split -> tag -> persist -> seed review items."""
    # 1. Extract text
    raw_text = extract_text_from_file(filename, content, content_type)

    # 2. Derive course title
    if custom_title and custom_title.strip():
        course_title = custom_title.strip()
    else:
        # Strip extension and clean
        base = re.sub(r"\.[^.]+$", "", filename).replace("_", " ").replace("-", " ")
        course_title = base.strip().title() or "Uploaded Notes"

    # 3. Split into lessons
    lessons_data = split_into_lessons(raw_text, course_title)
    if not lessons_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not structure uploaded document into lessons.",
            headers={"X-Error-Code": "UPLOAD_SPLIT_FAILED"},
        )

    # 4. Assign topic tags
    assign_topic_tags(db, lessons_data, course_title)

    # 5. Persist Course
    slug = f"upload-{_slugify(course_title)}-{uuid.uuid4().hex[:6]}"
    total_hours = max(1, round(sum(l.get("estimated_minutes", 10) for l in lessons_data) / 60))

    course = Course(
        id=uuid.uuid4(),
        title=course_title[:255],
        slug=slug,
        description=f"Personal notes course created from {filename}",
        subject="Uploaded Notes",
        difficulty="intermediate",
        estimated_hours=total_hours,
        is_published=True,  # Published so user can study lessons
        source="uploaded",
        is_private=True,   # Private to creator (plan.md §3, §6.13)
        created_by=user_id,
        created_at=_now(),
    )
    db.add(course)
    db.flush()

    # 6. Persist Lessons
    created_lessons: list[Lesson] = []
    unique_topics: set[str] = set()
    first_lesson_per_topic: dict[str, uuid.UUID] = {}

    for l_data in lessons_data:
        lesson = Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            title=l_data["title"],
            order_index=l_data["order_index"],
            content_md=l_data["content_md"],
            estimated_minutes=l_data.get("estimated_minutes", 10),
            topic_tags=l_data["topic_tags"],
            created_at=_now(),
        )
        db.add(lesson)
        created_lessons.append(lesson)
        for t in l_data["topic_tags"]:
            unique_topics.add(t)
            if t not in first_lesson_per_topic:
                first_lesson_per_topic[t] = lesson.id

    db.flush()

    # 7. Auto-enroll user in their private course
    existing_enr = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user_id, Enrollment.course_id == course.id)
        .first()
    )
    if not existing_enr:
        db.add(
            Enrollment(
                id=uuid.uuid4(),
                user_id=user_id,
                course_id=course.id,
                enrolled_at=_now(),
            )
        )

    # 8. Seed review_items for each unique topic (plan.md §6.13)
    due_date = _now() + timedelta(days=1)
    for topic_tag in unique_topics:
        source_lesson_id = first_lesson_per_topic.get(topic_tag)
        existing_item = (
            db.query(ReviewItem)
            .filter(
                ReviewItem.user_id == user_id,
                ReviewItem.topic_tag == topic_tag,
                ReviewItem.source_lesson_id == source_lesson_id,
            )
            .first()
        )
        if not existing_item:
            db.add(
                ReviewItem(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    topic_tag=topic_tag,
                    source_lesson_id=source_lesson_id,
                    due_at=due_date,
                    interval_days=1,
                    streak=0,
                )
            )

    db.commit()
    db.refresh(course)

    # 9. Emit events
    try:
        emit(db, user_id, "course.enrolled", {"course_id": str(course.id)})
        emit(
            db,
            user_id,
            "course.generated",
            {
                "course_id": str(course.id),
                "slug": course.slug,
                "lessons": len(created_lessons),
                "topics": sorted(unique_topics),
            },
        )
    except Exception as exc:
        logger.warning("Event emission after note upload failed: %s", exc)

    logger.info(
        "Successfully created uploaded course %r (%d lessons) for user %s",
        course.title,
        len(created_lessons),
        user_id,
    )

    return {
        "course": course.to_dict(),
        "lessons": [l.to_dict() for l in created_lessons],
        "topics": sorted(unique_topics),
    }
