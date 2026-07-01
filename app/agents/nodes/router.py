import json
import logging
from openai import AsyncOpenAI
from app.agents.state import GraphState
from app.core.config import settings
from app.core.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)


def get_recent_context(messages: list, n: int = 10) -> str:
    """Format the last n messages into a readable transcript for prompt context."""
    if not messages:
        return "No prior conversation."
    recent = messages[-n:]
    lines = []
    for m in recent:
        role = m.get("role", "user")
        content = m.get("content", "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "No prior conversation."


async def router_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    latest_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_message = msg.get("content", "")
            break

    context = get_recent_context(messages, n=10)

    try:
        prompt_content = render_prompt(
            "router",
            message=latest_message,
            history_summary=context
        )

        response = await client.chat.completions.create(
            model=settings.model_router,
            messages=[
                {"role": "user", "content": prompt_content}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "language": "english",
                "intent": "search",
                "occasion": None,
                "budget_lkr": None,
                "gift_recipient_gender": None,
                "gift_recipient_relation": None,
                "emotional_context": None,
                "requested_color": None,
                "exclude_kids": False
            }
        
        intent = result.get("intent", "search")
        lang = result.get("language", "english")
        order_number = result.get("order_number")
        my_steps = [{
            "type": "thinking",
            "step": "Routing",
            "detail": f"Detected: {intent}, {lang}",
            "status": "done"
        }]

        state_update: dict = {
            "language": lang,
            "intent": intent,
            "occasion": result.get("occasion"),
            "budget_lkr": result.get("budget_lkr"),
            "gift_recipient_gender": result.get("gift_recipient_gender"),
            "gift_recipient_relation": result.get("gift_recipient_relation"),
            "emotional_context": result.get("emotional_context"),
            "requested_color": result.get("requested_color"),
            "exclude_kids": result.get("exclude_kids", False),
            "thinking_steps": my_steps,
            "reflection_needed": False,
            "reflection_count": 0,
            "search_results": []
        }

        # For tracking intent: inject order number into messages so tracking_node can regex it
        if intent == "track" and order_number:
            state_update["messages"] = [{"role": "system", "content": f"ORDER_NUMBER:{order_number}"}]

        return state_update
    except Exception as e:
        logger.error(f"Router error: {e}")
        return {
            "language": "english",
            "intent": "search",
            "occasion": None,
            "budget_lkr": None,
            "thinking_steps": [{"type": "thinking", "step": "Routing", "detail": "Failed to parse routing", "status": "error"}],
            "reflection_needed": False,
            "reflection_count": 0,
            "search_results": []
        }

