"""Cross-module event bus.

OWNER: Member 4. USED BY: everyone. See plan.md 4.3.

This is the ONLY sanctioned coupling between modules. Emit an event and move on -
never import another member's service directly.

    from app.services.events import emit
    emit(db, user_id, "lesson.completed", {"lesson_id": str(lesson.id)})

Register a handler in your own module:

    from app.services.events import on

    @on("quiz.submitted")
    def update_mastery(db, user_id, payload):
        ...

Contract: emit() is best effort. A handler that raises is logged and swallowed -
it must NEVER fail the caller's request. M2's lesson completion cannot 500 because
a badge check has a bug.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("learnquest.events")

Handler = Callable[[Any, Any, dict], None]

# Every event type in the system. Adding one? Add it here and to plan.md 4.3.
EVENT_TYPES = {
    "lesson.completed",   # M2 -> {lesson_id, course_id, seconds}
    "quiz.submitted",     # M2 -> {quiz_id, score, correct, total}
    "course.enrolled",    # M2/M3 -> {course_id}
    "course.completed",   # M2 -> {course_id}
    "tutor.session",      # M1 -> {conversation_id, message_count}
    "quiz.generated",     # M1 -> {quiz_id, topic}
    "daily.login",        # M3 -> {}
}

HANDLERS: dict[str, list[Handler]] = {}


def on(event_type: str) -> Callable[[Handler], Handler]:
    """Decorator that registers a handler for an event type."""
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unknown event type {event_type!r}. Add it to EVENT_TYPES and plan.md 4.3."
        )

    def decorator(func: Handler) -> Handler:
        HANDLERS.setdefault(event_type, []).append(func)
        logger.debug("registered %s for %s", func.__name__, event_type)
        return func

    return decorator


def emit(db: Any, user_id: Any, event_type: str, payload: dict | None = None) -> None:
    """Fire an event. Synchronous, best effort, never raises."""
    payload = payload or {}

    if event_type not in EVENT_TYPES:
        logger.error("emit() called with unknown event type %r - ignored.", event_type)
        return

    handlers = HANDLERS.get(event_type, [])
    if not handlers:
        logger.debug("event %s emitted with no handlers registered", event_type)
        return

    for handler in handlers:
        try:
            handler(db, user_id, payload)
        except Exception:  # noqa: BLE001 - deliberate: never break the caller
            logger.exception(
                "handler %s failed for event %s (user=%s)",
                getattr(handler, "__name__", handler),
                event_type,
                user_id,
            )


def registered_handlers() -> dict[str, list[str]]:
    """Debug helper: which handlers are wired to which events."""
    return {
        event: [getattr(h, "__name__", repr(h)) for h in handlers]
        for event, handlers in HANDLERS.items()
    }
