"""AI tutor conversations.

OWNER: Member 1. See plan.md 6.3.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


@router.post("/conversations")
def create_conversation(user: CurrentUser, payload: dict | None = None) -> dict:
    # TODO(M1): insert a conversations row, optionally bound to a lesson/course.
    return {"id": None, "title": "New conversation"}


@router.get("/conversations")
def list_conversations(user: CurrentUser, page: int = 1, page_size: int = 20) -> dict:
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, user: CurrentUser) -> dict:
    return {"items": []}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, user: CurrentUser, payload: dict) -> dict:
    """Non-streaming reply plus the avatar payload."""
    # TODO(M1): build context, call get_llm().complete(), persist both messages,
    # summarise past 16 turns, emit("tutor.session", ...).
    return {"reply": "", "audio_url": None, "visemes": None}


@router.get("/conversations/{conversation_id}/stream")
async def stream_message(conversation_id: str, user: CurrentUser, q: str = "") -> dict:
    """SSE token stream. Use StreamingResponse(media_type="text/event-stream")."""
    # TODO(M1): replace this stub with a real StreamingResponse.
    return {"detail": "Not implemented", "code": "NOT_IMPLEMENTED"}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user: CurrentUser) -> dict:
    return {"deleted": False}


@router.post("/explain")
async def explain(user: CurrentUser, payload: dict) -> dict:
    """Explain a highlighted selection from a lesson. Called by M2's lesson viewer.

    Body: {lesson_id, selection}
    """
    # TODO(M1): short, spoken-friendly explanation grounded in the lesson content.
    return {"explanation": "", "audio_url": None, "visemes": None}
