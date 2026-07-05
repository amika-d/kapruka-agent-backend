import re

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


def _normalize(s: str) -> str:
    """Lowercase + collapse whitespace for fuzzy comparison."""
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_product_names(response: str, product_names: list[str]) -> str:
    """
    Scan the LLM response for text between asterisks (**name**) or quotes ("name" / 'name')
    that looks like a product name. If it doesn't match any real product name (case-insensitive,
    normalised whitespace), replace it with the safe fallback 'my pick below'.
    """
    if not product_names:
        return response

    normalised_real = {_normalize(n) for n in product_names}

    def replace_if_hallucinated(m: re.Match) -> str:
        full_match = m.group(0)
        inner = m.group(1)
        # Only act on reasonably product-name-like strings (≥4 chars, not a sentence)
        if len(inner) < 4 or len(inner.split()) > 10:
            return full_match
        if _normalize(inner) in normalised_real:
            return full_match  # Exact match — keep as-is
        # Not in the real list — replace with safe fallback
        logger.warning("Hallucinated product name removed: %r", inner)
        return "my pick below"

    # Match **bold**, "double-quoted", and 'single-quoted' spans
    response = re.sub(r'\*\*([^*]+)\*\*', replace_if_hallucinated, response)
    response = re.sub(r'"([^"]{4,80})"', replace_if_hallucinated, response)
    response = re.sub(r"'([^']{4,80})'", replace_if_hallucinated, response)

    return response


async def concierge_node(state: GraphState) -> dict:
    my_steps = [{"type": "thinking", "step": "Formatting", "detail": "Crafting response...", "status": "done"}]

    session_id = state.get("session_id", "default")
    session_data = db.get_session(session_id)
    rejected_products = session_data.get("rejected_products", [])
    search_results = state.get("search_results", [])
    products_exist = len(search_results) > 0
    product_names = [p.get("name", "") for p in search_results[:5]]

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
        pay_link=state.get("pay_link"),
        cart_issues=state.get("cart_issues"),
        order_status=state.get("order_status"),
        intent=state.get("intent"),
        products_exist=products_exist,
        product_names=product_names,
        recent_context=recent_context,
        delivery_result=state.get("delivery_result")
    )

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
        raw_response = response.choices[0].message.content
        # Scrub any hallucinated product names before sending to the user
        final_response = validate_product_names(raw_response, product_names)
    except Exception as e:
        logger.error(f"Concierge error: {e}")
        final_response = "I encountered an error while trying to respond."

    return {
        "final_response": final_response,
        "thinking_steps": my_steps
    }
