# src/api/v1/chat.py
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.schemas import ChatRequest
from app.agents.graph import compiled_graph
from app.core.database import SessionStore
from uuid import uuid4

router = APIRouter()
from app.core.database import get_session_store
store = get_session_store()

async def event_generator(request: ChatRequest):
    try:
        # Get session history
        session = store.get_session(request.session_id)
        
        # Build initial state
        initial_state = {
            "messages": session["messages"] + [
                {"role": "user", "content": request.message}
            ],
            "session_id": request.session_id,
            "cart": request.cart or [],
            "language": "english",
            "occasion": None,
            "intent": None,
            "image_context": None,
            "delivery_city": session.get("delivery_city"),
            "delivery_date": None,
            "search_results": [],
            "reflection_needed": False,
            "reflection_count": 0,
            "thinking_steps": [],
            "final_response": None,
        }

        # Run graph and stream thinking events
        # Wait, there's a small typo in the original uuid, I'll fix it if needed (it had: `uuid.uuid4()`, but didn't import `uuid`. It imported `uuid4` from `uuid`. Wait, it used `request.session_id_{uuid.uuid4()}`. `uuid` module is not imported. Let me just use `uuid4()`)
        config = {"configurable": {"thread_id": f"{request.session_id}_{uuid4()}"}}
        
        seen_step_keys = set()
        
        async for event in compiled_graph.astream(
            initial_state, 
            config=config,
            stream_mode="updates"
        ):
            for node_name, node_output in event.items():
                
                # Stream thinking steps as they come
                for step in node_output.get("thinking_steps", []):
                    key = f"{step.get('step')}_{step.get('detail')}"
                    if key not in seen_step_keys:
                        seen_step_keys.add(key)
                        # Flat shape: {type, step, detail, status}
                        yield f"data: {json.dumps({'type': 'thinking', 'step': step.get('step'), 'detail': step.get('detail'), 'status': step.get('status', 'done')})}\n\n"
                        await asyncio.sleep(0)

                # Stream search results as product carousel
                if node_output.get("search_results"):
                    products = node_output["search_results"]
                    print(f"STREAMING CAROUSEL — image_urls: {[p.get('image_url') for p in products]}")
                    ui_payload = {
                        "type": "ui",
                        "component": "ProductCarousel",
                        "props": {"items": products}
                    }
                    yield f"data: {json.dumps(ui_payload)}\n\n"
                    await asyncio.sleep(0)

                # Stream tracking card
                if node_output.get("order_status"):
                    yield f"data: {json.dumps({'type': 'tracking_card', 'data': node_output['order_status']})}\n\n"
                    await asyncio.sleep(0)

                # Stream pay link
                if node_output.get("pay_link"):
                    yield f"data: {json.dumps({'type': 'pay_link', 'url': node_output['pay_link']})}\n\n"
                    await asyncio.sleep(0)

                # Stream final text response word by word
                if node_output.get("final_response"):
                    response = node_output["final_response"]
                    for word in response.split():
                        yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
                        await asyncio.sleep(0.04)
        
        # Update session memory
        store.append_message(request.session_id, {
            "role": "user", "content": request.message
        })
        if initial_state.get("final_response"):
            store.append_message(request.session_id, {
                "role": "assistant", 
                "content": initial_state["final_response"]
            })
        
        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

@router.post("/chat")
async def stream_chat(request: ChatRequest):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions")
async def list_sessions():
    """Return a list of all saved chat sessions with their title and timestamp."""
    sessions = store.list_all_session_details()
    result = []
    for s in sessions:
        messages = s.get("messages", [])
        # Title = first user message, truncated
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
async def get_session(session_id: str):
    """Return the full message history for a specific session."""
    session = store.get_session(session_id)
    return {
        "session_id": session_id,
        "messages": session.get("messages", []),
        "last_accessed": session.get("last_accessed"),
    }