# src/api/v1/chat.py
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.schemas import ChatRequest
from app.agents.graph import compiled_graph
from app.core.database import SessionStore
from app.core.config import settings
from app.core.prompt_loader import render_prompt
from openai import AsyncOpenAI
from uuid import uuid4

router = APIRouter()
from app.core.database import get_session_store
store = get_session_store()

vision_client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)

async def extract_vision_context(image_base64: str, language: str = "english") -> str:
    """Run vision model on uploaded image before main graph."""
    vision_prompt = render_prompt("vision", language=language)
    
    response = await vision_client.chat.completions.create(
        model=settings.model_vision,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": vision_prompt
                }
            ]
        }],
        max_tokens=300
    )
    
    return response.choices[0].message.content

async def event_generator(request: ChatRequest):
    try:
        # Get session history
        session = store.get_session(request.session_id)
        
        # Extract vision context BEFORE building initial_state
        image_context = None
        if request.image_base64:
            yield f"data: {json.dumps({'type': 'thinking', 'step': 'Vision', 'detail': 'Analyzing your image...', 'status': 'running'})}\n\n"
            await asyncio.sleep(0)
            try:
                image_context = await extract_vision_context(request.image_base64)
                detail_preview = image_context[:80] + "..." if len(image_context) > 80 else image_context
                yield f"data: {json.dumps({'type': 'thinking', 'step': 'Vision', 'detail': detail_preview, 'status': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'thinking', 'step': 'Vision', 'detail': f'Vision analysis failed: {str(e)}', 'status': 'error'})}\n\n"
            await asyncio.sleep(0)
        
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
            "image_context": image_context,
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
        final_text = ""
        collected_thinking: list[dict] = []
        last_ui_payload: dict | None = None
        
        async for event in compiled_graph.astream(
            initial_state, 
            config=config,
            stream_mode="updates"
        ):
            for node_name, node_output in event.items():
                
                # Stream thinking steps as they come
                for step in node_output.get("thinking_steps", []):
                    step_name = step.get("step") or ""
                    step_detail = step.get("detail") or ""
                    key = f"{step_name}_{step_detail}"
                    if key not in seen_step_keys:
                        seen_step_keys.add(key)
                        collected_thinking.append({
                            "step": step.get("step"),
                            "detail": step.get("detail"),
                            "status": step.get("status", "done")
                        })
                        # Flat shape: {type, step, detail, status}
                        yield f"data: {json.dumps({'type': 'thinking', 'step': step_name, 'detail': step_detail, 'status': step.get('status', 'done')})}\n\n"
                        await asyncio.sleep(0)

                # Stream search results as product carousel
                if node_output.get("search_results"):
                    products = node_output["search_results"]
                    print(f"STREAMING CAROUSEL — image_urls: {[p.get('image_url') for p in products]}")
                    last_ui_payload = {
                        "component": "ProductCarousel",
                        "props": {"items": products}
                    }
                    ui_payload = {
                        "type": "ui",
                        "component": "ProductCarousel",
                        "props": {"items": products}
                    }
                    yield f"data: {json.dumps(ui_payload)}\n\n"
                    await asyncio.sleep(0)

                # Stream order tracking as OrderTimeline UI component
                if node_output.get("order_status"):
                    order_status = node_output["order_status"]
                    last_ui_payload = {
                        "component": "OrderTimeline", 
                        "props": {"orderStatus": order_status}
                    }
                    yield f"data: {json.dumps({'type': 'ui', 'component': 'OrderTimeline', 'props': {'orderStatus': order_status}})}\n\n"
                    await asyncio.sleep(0)

                # Stream pay link
                if node_output.get("pay_link"):
                    yield f"data: {json.dumps({'type': 'pay_link', 'url': node_output['pay_link']})}\n\n"
                    await asyncio.sleep(0)

                # Stream final text response word by word
                if node_output.get("final_response"):
                    final_text = node_output["final_response"]
                    for word in final_text.split():
                        yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
                        await asyncio.sleep(0.04)
        
        # Update session memory
        store.append_message(request.session_id, {
            "role": "user", "content": request.message
        })
        if final_text or collected_thinking or last_ui_payload:
            assistant_msg = {
                "role": "assistant",
                "content": final_text
            }
            if collected_thinking:
                assistant_msg["thinking"] = collected_thinking
            if last_ui_payload:
                assistant_msg["ui"] = last_ui_payload
            store.append_message(request.session_id, assistant_msg)
        
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

