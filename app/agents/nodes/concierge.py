from openai import AsyncOpenAI
import logging
from app.agents.state import GraphState
from app.core.config import settings
from app.core.prompt_loader import render_prompt
from app.core.database import get_session_store
from app.agents.nodes.router import get_recent_context

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)

db = get_session_store()

async def concierge_node(state: GraphState) -> dict:
    my_steps = []
    my_steps.append({
        "type": "thinking",
        "step": "Formatting",
        "detail": "Crafting response...",
        "status": "done"
    })
    
    session_id = state.get("session_id", "default")
    session_data = db.get_session(session_id)
    rejected_products = session_data.get("rejected_products", [])

    messages = state.get("messages", [])
    recent_context = get_recent_context(messages, n=8)

    prompt = render_prompt(
        "concierge",
        language=state.get("language", "english"),
        occasion=state.get("occasion", "everyday"),
        delivery_city=state.get("delivery_city"),
        delivery_date=state.get("delivery_date"),
        gift_recipient_gender=state.get("gift_recipient_gender"),
        gift_recipient_relation=state.get("gift_recipient_relation"),
        emotional_context=state.get("emotional_context"),
        rejected_products=rejected_products,
        cart_count=len(state.get("cart", [])),
        image_context=state.get("image_context"),
        recent_context=recent_context
    )

    # Build full message history for the LLM (not just the latest message)
    llm_messages = [{"role": "system", "content": prompt}]
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            llm_messages.append({"role": role, "content": content})

    try:
        response = await client.chat.completions.create(
            model=settings.model_concierge,
            messages=llm_messages
        )
        final_response = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Concierge error: {e}")
        final_response = "I encountered an error while trying to respond."
    
    return {
        "final_response": final_response,
        "thinking_steps": my_steps
    }

