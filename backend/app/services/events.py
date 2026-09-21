"""Cross-module event bus for LearnQuest AI.

OWNER: Member 4 (Gamification & Analytics).
USED BY: All members (M1, M2, M3, M4).
REFERENCE: plan.md §4.3, §9.1.

This event bus provides a decoupled, synchronous, best-effort mechanism for
application components to broadcast domain events without directly importing
or depending on other modules.

Example - Emitting an event (e.g. from M2 lesson completion):
    from app.services.events import emit

    emit(
        db=db,
        user_id=user.id,
        event_type="lesson.completed",
        payload={"lesson_id": str(lesson.id), "course_id": str(course.id), "seconds": 120},
    )

Example - Registering an event handler (e.g. in M4 XP engine or M1 Mastery):
    from app.services.events import register_handler

    @register_handler("lesson.completed")
    def handle_lesson_completed(db, user_id, payload):
        # Award XP, update streak, check achievements
        ...

Safety Guarantee:
    emit() is best-effort. Every handler is executed synchronously within an isolated
    try/except block. Any exception raised by a handler is logged and swallowed,
    guaranteeing that a failure in a secondary handler (such as an analytics or
    gamification bug) will NEVER fail or crash the primary caller's request (e.g.
    lesson submission or authentication).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("learnquest.events")

# Handler callable type: (db_session, user_id, payload_dict) -> Any
Handler = Callable[[Any, Any, dict[str, Any]], Any]


class EventType:
    """Standard event types defined across LearnQuest modules (plan.md §4.3)."""

    LESSON_COMPLETED = "lesson.completed"  # Emitted by M2 -> {lesson_id, course_id, seconds}
    QUIZ_SUBMITTED = "quiz.submitted"      # Emitted by M2 -> {quiz_id, score, correct, total}
    COURSE_ENROLLED = "course.enrolled"    # Emitted by M2/M3 -> {course_id}
    COURSE_COMPLETED = "course.completed"  # Emitted by M2 -> {course_id}
    TUTOR_SESSION = "tutor.session"        # Emitted by M1 -> {conversation_id, message_count}
    QUIZ_GENERATED = "quiz.generated"      # Emitted by M1 -> {quiz_id, topic}
    DAILY_LOGIN = "daily.login"            # Emitted by M3 -> {}
    STREAK_UPDATED = "streak.updated"      # Emitted by M4 -> {current_streak, longest_streak}
    BADGE_EARNED = "badge.earned"          # Emitted by M4 -> {badge_code, badge_name}
    ROADMAP_NODE_COMPLETED = "roadmap.node_completed"  # Emitted by M1 -> {node_id}


# Standard set of known event types in the platform
EVENT_TYPES: set[str] = {
    EventType.LESSON_COMPLETED,
    EventType.QUIZ_SUBMITTED,
    EventType.COURSE_ENROLLED,
    EventType.COURSE_COMPLETED,
    EventType.TUTOR_SESSION,
    EventType.QUIZ_GENERATED,
    EventType.DAILY_LOGIN,
    EventType.STREAK_UPDATED,
    EventType.BADGE_EARNED,
    EventType.ROADMAP_NODE_COMPLETED,
}

# In-memory registry mapping event_type -> list of subscriber handlers
HANDLERS: dict[str, list[Handler]] = {}


def register_handler(event_type: str) -> Callable[[Handler], Handler]:
    """Decorator to register a function as an event handler for a specific event type.

    The decorated function should accept three parameters:
        handler(db: Session, user_id: UUID | str | Any, payload: dict[str, Any]) -> Any

    Args:
        event_type: The name of the event to subscribe to (e.g. 'lesson.completed').

    Returns:
        Callable decorator registering the function into HANDLERS registry.

    Example:
        @register_handler("lesson.completed")
        def on_lesson_completed(db, user_id, payload):
            award_xp(db, user_id, 50)
    """
    if event_type not in EVENT_TYPES:
        logger.warning(
            "Registering handler for non-standard event type %r. "
            "If this is a new core event, consider adding it to EventType / plan.md §4.3.",
            event_type,
        )
        EVENT_TYPES.add(event_type)

    def decorator(func: Handler) -> Handler:
        handlers = HANDLERS.setdefault(event_type, [])
        if func not in handlers:
            handlers.append(func)
            logger.debug(
                "Registered handler %s for event %s",
                getattr(func, "__name__", repr(func)),
                event_type,
            )
        return func

    return decorator


# Convenient alias to preserve compatibility with existing scaffold and plan.md §9.1
on = register_handler


def emit(
    db: Session | Any,
    user_id: UUID | str | int | Any,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> list[Any]:
    """Emit an application event synchronously to all registered handlers.

    Execution is synchronous and best-effort. Each handler is executed in its
    own try/except block so that failures in one handler do not disrupt the caller
    or prevent subsequent handlers from running.

    Args:
        db: Active SQLAlchemy database session (or None if unconfigured/mocked).
        user_id: Unique identifier of the user associated with the event.
        event_type: String identifier of the event being emitted.
        payload: Optional dictionary containing event details and context.

    Returns:
        list[Any]: Return values from all successfully executed handlers.
    """
    if payload is None:
        payload = {}

    if event_type not in EVENT_TYPES and event_type not in HANDLERS:
        logger.warning(
            "emit() called with unknown event type %r - no handlers executed.",
            event_type,
        )
        return []

    handlers = HANDLERS.get(event_type, [])
    if not handlers:
        logger.debug("Event %r emitted with no handlers registered.", event_type)
        return []

    results: list[Any] = []
    for handler in handlers:
        handler_name = getattr(handler, "__name__", repr(handler))
        try:
            result = handler(db, user_id, payload)
            results.append(result)
        except Exception:
            # Deliberate catch-all: NEVER allow a handler failure to break the primary caller
            logger.exception(
                "Handler %r failed for event %r (user_id=%s, payload=%s)",
                handler_name,
                event_type,
                user_id,
                payload,
            )

    return results


def registered_handlers() -> dict[str, list[str]]:
    """Return a mapping of registered event types to handler function names.

    Useful for inspection, logging, and debugging.
    """
    return {
        event: [getattr(h, "__name__", repr(h)) for h in handlers]
        for event, handlers in HANDLERS.items()
    }


def get_handlers(event_type: str) -> list[Handler]:
    """Return a shallow copy of the list of handlers registered for an event type."""
    return list(HANDLERS.get(event_type, []))


def unregister_handler(event_type: str, handler: Handler) -> bool:
    """Unregister a specific handler from an event type.

    Returns:
        bool: True if the handler was found and removed, False otherwise.
    """
    handlers = HANDLERS.get(event_type)
    if handlers and handler in handlers:
        handlers.remove(handler)
        if not handlers:
            HANDLERS.pop(event_type, None)
        return True
    return False


def clear_handlers(event_type: str | None = None) -> None:
    """Clear registered handlers.

    Args:
        event_type: If specified, clears handlers only for this event.
                    If None, clears all registered handlers across all events.
    """
    if event_type is not None:
        HANDLERS.pop(event_type, None)
    else:
        HANDLERS.clear()
