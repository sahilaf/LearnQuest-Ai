"""AI tutor conversations router.

OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
See plan.md §6.3, §6.7.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser
from app.models.ai import Conversation, Message
from app.models.course import Course, Lesson
from app.services.events import emit
from app.services.llm_client import get_llm
from app.services.prompts import (
    EXPLAIN_QUESTION_PROMPT,
    EXPLAIN_SELECTION_PROMPT,
    SUMMARISE_AFTER_MESSAGES,
    build_tutor_context,
    generate_conversation_title,
)

logger = logging.getLogger("learnquest.tutor")

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


def _next_conversation_number(db: Session, user_id: uuid.UUID) -> int:
    """The next free number for this user, counting from 1.

    Gaps left by deleted conversations are not reused: reusing one would make an
    old bookmark silently open a different conversation.
    """
    highest = (
        db.query(func.max(Conversation.number))
        .filter(Conversation.user_id == user_id)
        .scalar()
    )
    return int(highest or 0) + 1


def _resolve_conversation(
    db: Session, user_id: uuid.UUID, ref: str | uuid.UUID
) -> Conversation | None:
    """Find a conversation by its per-user number or by its UUID.

    Both forms are accepted so that links already shared as UUIDs keep working;
    `number` is only what the URL shows from now on.
    """
    query = db.query(Conversation).filter(Conversation.user_id == user_id)

    # Callers reach this from a path string, but the endpoints are also invoked
    # directly in tests with a real UUID, so normalise rather than assume.
    if isinstance(ref, uuid.UUID):
        return query.filter(Conversation.id == ref).first()

    text = str(ref).strip()
    if text.isdigit():
        return query.filter(Conversation.number == int(text)).first()

    try:
        return query.filter(Conversation.id == uuid.UUID(text)).first()
    except ValueError:
        return None


def _require_conversation(
    db: Session | None, user_id: uuid.UUID, ref: str | uuid.UUID
) -> Conversation:
    conversation = _resolve_conversation(db, user_id, ref) if db is not None else None
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


class CreateConversationRequest(BaseModel):
    title: str | None = None
    context_lesson_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    context_course_id: uuid.UUID | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class ExplainRequest(BaseModel):
    selection: str = Field(..., min_length=1, max_length=2000)
    lesson_id: uuid.UUID | None = None
    # The lesson viewer offers a free-text question box. Without this the
    # question was being sent *as* the selection, so the prompt told the model
    # the student had highlighted their own question.
    question: str | None = Field(default=None, max_length=2000)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    user: CurrentUser,
    body: CreateConversationRequest | None = None,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Create a new conversation thread with the AI tutor."""
    user_id = uuid.UUID(user["id"])
    title = body.title if (body and body.title) else "New conversation"
    context_lesson_id = (
        (body.context_lesson_id or body.lesson_id) if body else None
    )
    context_course_id = body.context_course_id if body else None

    # If lesson is provided but not course, derive course from lesson
    if context_lesson_id and not context_course_id and db is not None:
        lesson = db.query(Lesson).filter(Lesson.id == context_lesson_id).first()
        if lesson:
            context_course_id = lesson.course_id

    now = datetime.now(timezone.utc)
    conv_id = uuid.uuid4()

    if db is not None:
        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            number=_next_conversation_number(db, user_id),
            title=title,
            context_lesson_id=context_lesson_id,
            context_course_id=context_course_id,
            created_at=now,
            updated_at=now,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv.to_dict()

    # Fallback when DB is not configured
    return {
        "id": str(conv_id),
        "user_id": str(user_id),
        "title": title,
        "context_lesson_id": str(context_lesson_id) if context_lesson_id else None,
        "context_course_id": str(context_course_id) if context_course_id else None,
        "summary": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@router.get("/conversations")
def list_conversations(
    user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """List student's conversations paginated, newest first."""
    user_id = uuid.UUID(user["id"])

    if db is not None:
        query = db.query(Conversation).filter(Conversation.user_id == user_id)
        total = query.count()
        items = (
            query.order_by(Conversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [c.to_dict() for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve conversation details."""
    user_id = uuid.UUID(user["id"])

    if db is not None:
        conv = _require_conversation(db, user_id, conversation_id)
        return conv.to_dict()

    return {
        "id": str(conversation_id),
        "user_id": str(user_id),
        "title": "Mock Conversation",
        "summary": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve message history for a conversation."""
    user_id = uuid.UUID(user["id"])

    if db is not None:
        conv = _require_conversation(db, user_id, conversation_id)

        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .all()
        )
        return {"items": [m.to_dict() for m in messages]}

    return {"items": []}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Send a message to the AI tutor and receive its reply.

    The avatar speaks this text through /api/avatar/speech; the reply carries
    no timing data of its own.
    """
    user_id = uuid.UUID(user["id"])
    content = body.content.strip()
    now = datetime.now(timezone.utc)

    conv: Conversation | None = None
    if db is not None:
        conv = _require_conversation(db, user_id, conversation_id)

        # Auto-title from the first user message if still default
        if conv.title == "New conversation":
            conv.title = generate_conversation_title(content)

        # 1. Save user message
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content=content,
            tokens=max(1, len(content) // 4),
            created_at=now,
        )
        db.add(user_msg)
        db.flush()

    # 2. Build full context (system prompt, profile, lesson material, memory, recent turns)
    context_messages = build_tutor_context(
        db=db,
        user_id=user_id,
        conversation_id=conv.id,
    )
    # Ensure current user turn is at the end of context
    if not context_messages or context_messages[-1].get("content") != content:
        context_messages.append({"role": "user", "content": content})

    # 3. Call LLM
    llm = get_llm()
    try:
        reply = await llm.complete(context_messages, temperature=0.7, max_tokens=600)
    except Exception as exc:
        logger.error("LLM completion failed: %s (falling back to MockLLMClient)", exc)
        from app.services.llm_client import MockLLMClient

        reply = await MockLLMClient().complete(
            context_messages, temperature=0.7, max_tokens=600
        )

    # 5. Persist assistant reply
    assistant_msg_id = uuid.uuid4()
    if db is not None and conv is not None:
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            tokens=max(1, len(reply) // 4),
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        conv.updated_at = datetime.now(timezone.utc)

        # 6. Check rolling summarisation (plan.md 6.3)
        total_msgs = (
            db.query(Message).filter(Message.conversation_id == conv.id).count()
        )
        if total_msgs >= SUMMARISE_AFTER_MESSAGES and not conv.summary:
            try:
                earlier_msgs = (
                    db.query(Message)
                    .filter(Message.conversation_id == conv.id)
                    .order_by(Message.created_at.asc())
                    .limit(8)
                    .all()
                )
                summary_prompt = [
                    {
                        "role": "system",
                        "content": "Summarize the key topics and learner questions in 2-3 sentences for memory:",
                    },
                    {
                        "role": "user",
                        "content": "\n".join(f"{m.role}: {m.content}" for m in earlier_msgs),
                    },
                ]
                summary_text = await llm.complete(summary_prompt, max_tokens=150)
                conv.summary = summary_text.strip()
            except Exception as e:
                logger.warning("Rolling summarisation failed: %s", e)

        db.commit()

        # 7. Emit tutor session event for M4 gamification
        emit(
            db=db,
            user_id=user_id,
            event_type="tutor.session",
            payload={
                "conversation_id": str(conv.id),
                "message_count": total_msgs,
            },
        )

    return {
        "id": str(assistant_msg_id),
        "conversation_id": str(conv.id),
        "role": "assistant",
        "content": reply,
        "reply": reply,  # backward compatibility with earlier stubs
        "audio_url": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Delete a conversation."""
    user_id = uuid.UUID(user["id"])

    if db is not None:
        conv = _require_conversation(db, user_id, conversation_id)
        db.delete(conv)
        db.commit()
        return {"deleted": True, "id": str(conv.id), "number": conv.number}

    return {"deleted": True, "id": conversation_id}


@router.post("/explain")
async def explain(
    body: ExplainRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Explain a highlighted selection from a lesson.

    Called by Member 2's lesson viewer when a student clicks 'Ask Tutor'.
    """
    lesson_title = "Current Lesson"
    if body.lesson_id and db is not None:
        lesson = db.query(Lesson).filter(Lesson.id == body.lesson_id).first()
        if lesson:
            lesson_title = lesson.title

    question = (body.question or "").strip()
    if question:
        prompt = EXPLAIN_QUESTION_PROMPT.format(
            lesson_title=lesson_title,
            selection=body.selection,
            question=question,
        )
    else:
        prompt = EXPLAIN_SELECTION_PROMPT.format(
            lesson_title=lesson_title,
            selection=body.selection,
        )

    llm = get_llm()
    try:
        explanation = await llm.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250,
        )
    except Exception as exc:
        logger.error("Explain selection failed: %s", exc)
        explanation = (
            f"Here is a simple way to look at '{body.selection[:50]}...': "
            "Think of it as a key building block that connects your previous knowledge to this topic."
        )

    return {
        "explanation": explanation,
        "selection": body.selection,
        "audio_url": None,
    }


# --------------------------------------------------------------------------- #
# Teach-Back - the protege loop. See services/teachback.py.
# --------------------------------------------------------------------------- #
#
# Mounted under /api/tutor rather than in a router of its own so that
# app/main.py - a shared file - does not need another registration line.


class TeachBackStartRequest(BaseModel):
    # Omit to teach the most recently captured misconception still standing.
    topic_tag: str | None = Field(default=None, max_length=100)


class TeachBackTeachRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


def _teachback_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    return db


def _load_teachback(db: Session, session_id: uuid.UUID, user_id: uuid.UUID):
    from app.models.ai import TeachBackSession

    session = (
        db.query(TeachBackSession)
        .filter(
            TeachBackSession.id == session_id,
            TeachBackSession.user_id == user_id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teach-Back session not found.",
        )
    return session


@router.get("/teachback/available")
def teachback_available(
    user: CurrentUser, db: Session | None = Depends(get_db)
) -> dict[str, Any]:
    """Misconceptions this student could currently teach Nova out of.

    Drives the entry point: with nothing here there is nothing to teach, which
    is the normal state until a quiz has been answered wrongly.
    """
    from app.models.ai import TopicMastery
    from app.services.mastery import misconception_status

    database = _teachback_db(db)
    user_id = uuid.UUID(user["id"])

    rows = (
        database.query(TopicMastery)
        .filter(
            TopicMastery.user_id == user_id,
            TopicMastery.misconception.isnot(None),
            TopicMastery.misconception_cleared_at.is_(None),
        )
        .order_by(TopicMastery.misconception_updated_at.desc().nullslast())
        .all()
    )

    return {
        "items": [
            {
                "topic_tag": r.topic_tag,
                "misconception": r.misconception,
                "status": misconception_status(r),
                "mastery_score": float(r.mastery_score or 0),
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.post("/teachback/start", status_code=status.HTTP_201_CREATED)
async def teachback_start(
    body: TeachBackStartRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Open a Teach-Back round: Nova is seeded with the student's own false belief."""
    from app.services.teachback import start_session

    database = _teachback_db(db)
    user_id = uuid.UUID(user["id"])

    session, error = await start_session(database, user_id, body.topic_tag)

    if error == "no_misconception":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No misconception to teach yet. Answer a quiz question wrongly and "
                "the tutor will name the belief behind it first."
            ),
        )
    if error == "no_question":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not find or generate a question to test this misconception.",
        )

    return session.to_dict()


@router.get("/teachback/{session_id}")
def teachback_get(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Current state of one Teach-Back session."""
    database = _teachback_db(db)
    session = _load_teachback(database, session_id, uuid.UUID(user["id"]))
    return session.to_dict()


@router.post("/teachback/{session_id}/teach")
async def teachback_teach(
    session_id: uuid.UUID,
    body: TeachBackTeachRequest,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """The student explains. Nova pushes back, or concedes the point."""
    from app.services.teachback import student_turn

    database = _teachback_db(db)
    session = _load_teachback(database, session_id, uuid.UUID(user["id"]))

    if session.status in ("passed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This session is already {session.status}.",
        )

    result = await student_turn(database, session, body.message)
    result["session"] = session.to_dict()
    return result


@router.post("/teachback/{session_id}/retake")
async def teachback_retake(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Nova re-takes the question. Her score is the student's grade."""
    from app.services.teachback import retake

    database = _teachback_db(db)
    session = _load_teachback(database, session_id, uuid.UUID(user["id"]))

    result = await retake(database, session)

    error = result.get("error")
    if error == "nothing_taught":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teach Nova something before asking her to re-take the question.",
        )
    if error == "session_closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This session is already {result.get('status')}.",
        )
    if error == "nova_unavailable":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The tutor could not answer just now. Try the retake again.",
        )

    result["session"] = session.to_dict()
    return result
