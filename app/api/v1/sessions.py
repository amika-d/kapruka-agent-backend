from fastapi import APIRouter
from app.core.database import get_session_store

router = APIRouter()

@router.get("/sessions")
async def list_sessions():
    """Return a list of all saved chat sessions with their title and timestamp."""
    store = get_session_store()
    sessions = store.list_all_session_details()
    result = []
    for s in sessions:
        messages = s.get("messages", [])
        title = next(
            (m["content"][:60] for m in messages if m.get("role") == "user"),
            "New Chat"
        )
        result.append({
            "session_id": s["session_id"],
            "title": title,
            "last_accessed": s["last_accessed"],
            "message_count": len(messages),
        })
    return result

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    store = get_session_store()
    # Use _sessions.get() to avoid creating a new session if it doesn't exist
    session = store._sessions.get(session_id)
    if not session:
        return {
            "messages": [],
            "delivery_city": None,
            "last_order_number": None
        }
    
    return {
        "messages": session.get("messages", []),
        "delivery_city": session.get("delivery_city"),
        "last_order_number": session.get("last_order_number")
    }
