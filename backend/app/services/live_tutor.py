"""Context and persistence for the live voice tutor. OWNER: Member 1.

The live tab talks to Gemini Live: the student speaks, the tutor answers in
speech within ~1.5s. That model gets no message list, only a system
instruction, so everything the chat tutor knows - level, weak topics, open
misconceptions, the lesson, the rolling summary and the recent turns - is
folded into that one instruction here, from the same `build_tutor_context`
the chat uses.

Each finished live turn is saved into the same conversation as ordinary
messages. That is what makes the tabs one tutor rather than three: say
something out loud, switch to Chat, and the chat tutor has it in its history.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from app.database import database_is_configured, get_session_factory
from app.models.ai import Conversation, Message
from app.services.prompts import build_tutor_context, generate_conversation_title

logger = logging.getLogger("learnquest.live")

# The live line Fydp_v2 runs on. Its native-audio siblings were measured there
# to slow from 8s to 66s per reply as a session grew; this one stays flat.
DEFAULT_LIVE_MODEL = "gemini-3.8-live"

# Rendered transcript of earlier turns is capped so a long thread cannot crowd
# out the lesson and the learner profile.
MAX_HISTORY_CHARS = 6000

LIVE_ADDENDUM = """
You are Redwan, LearnQuest's tutor, and this is a LIVE SPOKEN conversation: the
student talks to you through a microphone and hears your voice.
- Reply in one to three short spoken sentences. Sound like a person talking.
- Never use markdown, bullet points, symbols, code or URLs - they cannot be heard.
  Say code in words, briefly.
- Ask one question at a time, then stop and let the student answer.
- If you did not catch what the student said, ask them to repeat it.
- Speak English unless the student clearly asks for another language."""


def live_model() -> str:
    return os.getenv("LIVE_MODEL", DEFAULT_LIVE_MODEL)


def build_live_instruction(user_id: uuid.UUID, conversation_id: uuid.UUID | None) -> str:
    """One system instruction carrying the whole tutor context."""
    db = get_session_factory()() if database_is_configured() else None
    try:
        messages = build_tutor_context(db, user_id, conversation_id)
    finally:
        if db is not None:
            db.close()

    system = [m["content"] for m in messages if m["role"] == "system"]
    turns = [m for m in messages if m["role"] in ("user", "assistant")]

    parts = [system[0] if system else "", LIVE_ADDENDUM]
    parts.extend(system[1:])  # the rolling summary, when there is one

    if turns:
        lines: list[str] = []
        used = 0
        for m in reversed(turns):
            who = "Student" if m["role"] == "user" else "Tutor"
            line = f"{who}: {m['content'].strip()}"
            if used + len(line) > MAX_HISTORY_CHARS:
                break
            lines.append(line)
            used += len(line)
        parts.append(
            "Earlier in this conversation (typed or spoken, most recent last). "
            "Continue from here; do not greet the student again:\n"
            + "\n".join(reversed(lines))
        )
    return "\n\n".join(p for p in parts if p)


def resolve_conversation_id(user_id: uuid.UUID, ref: str | None) -> tuple[uuid.UUID | None, int | None]:
    """The conversation's UUID and number for a per-user number or UUID ref."""
    if not ref or not database_is_configured():
        return None, None
    from app.routers.tutor import _resolve_conversation

    db = get_session_factory()()
    try:
        conv = _resolve_conversation(db, user_id, str(ref))
        return (conv.id, conv.number) if conv else (None, None)
    finally:
        db.close()


def save_turn(conversation_id: uuid.UUID | None, user_text: str, tutor_text: str) -> None:
    """Persist one finished live exchange as ordinary chat messages."""
    user_text, tutor_text = user_text.strip(), tutor_text.strip()
    if conversation_id is None or not database_is_configured() or not (user_text or tutor_text):
        return
    db = get_session_factory()()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv is None:
            return
        now = datetime.now(timezone.utc)
        if user_text:
            if conv.title in ("New conversation", "Live conversation"):
                conv.title = generate_conversation_title(user_text)
            db.add(Message(id=uuid.uuid4(), conversation_id=conv.id, role="user",
                           content=user_text, tokens=max(1, len(user_text) // 4), created_at=now))
        if tutor_text:
            db.add(Message(id=uuid.uuid4(), conversation_id=conv.id, role="assistant",
                           content=tutor_text, tokens=max(1, len(tutor_text) // 4),
                           # strictly after the question, so history sorts right
                           created_at=now + timedelta(milliseconds=1)))
        conv.updated_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001 - a lost transcript must not end the call
        db.rollback()
        logger.warning("Could not save live turn: %s", exc)
    finally:
        db.close()
