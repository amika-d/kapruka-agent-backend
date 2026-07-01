import json
import logging
from openai import AsyncOpenAI
from app.agents.state import GraphState
from app.mcp.tools import (
    KAPRUKA_TOOL_SCHEMAS, kapruka_search_products, kapruka_get_product, 
    kapruka_list_categories, kapruka_list_delivery_cities, kapruka_check_delivery, 
    kapruka_create_order, kapruka_track_order, parse_search_results,
    parse_product_detail
)
from app.core.config import settings
from app.core.database import SessionStore
from app.core.prompt_loader import render_prompt
from app.core.category_cache import get_top_level_categories

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)

TOOL_MAP = {
    "kapruka_search_products": kapruka_search_products,
    "kapruka_get_product": kapruka_get_product,
    "kapruka_list_categories": kapruka_list_categories,
    "kapruka_list_delivery_cities": kapruka_list_delivery_cities,
    "kapruka_check_delivery": kapruka_check_delivery,
    "kapruka_create_order": kapruka_create_order,
    "kapruka_track_order": kapruka_track_order
}

from app.core.database import get_session_store
db = get_session_store()


def dedupe_products(products: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in products:
        pid = p.get("product_id")
        if pid and pid not in seen:
            seen.add(pid)
            unique.append(p)
    return unique


def is_relevant(product: dict, intent_context: dict) -> bool:
    name = product.get("name", "").lower()
    
    # Filter kids items if adult purchase
    kids_keywords = ["kids", "baby", "children", "toddler", 
                     "infant", "girl baby", "boy baby"]
    if intent_context.get("exclude_kids"):
        if any(k in name for k in kids_keywords):
            return False
    
    # Filter wrong color if color specified
    requested_color = intent_context.get("requested_color")
    if requested_color:
        color_variants = ["white", "blue", "red", "green", 
                          "pink", "olive", "yellow", "grey"]
        other_colors = [c for c in color_variants if c != requested_color]
        if any(c in name.lower() for c in other_colors):
            return False
    
    return True


async def shopper_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    my_steps = []
    search_results = []  # always fresh, never carried over from state
    session_id = state.get("session_id", "default")

    session_data = db.get_session(session_id)
    rejected_products = session_data.get("rejected_products", [])

    intent_context = {
        "requested_color": state.get("requested_color"),
        "exclude_kids": state.get("exclude_kids") or (
            state.get("gift_recipient_gender") in ["male", "female"]
            or state.get("emotional_context") in ["self_purchase", "self_purchase_male", "self_purchase_female"]
        )
    }

    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    categories = get_top_level_categories()

    system_prompt = render_prompt(
        "shopper",
        intent=state.get("intent"),
        occasion=state.get("occasion"),
        budget_lkr=state.get("budget_lkr"),
        delivery_city=state.get("delivery_city"),
        gift_recipient_gender=state.get("gift_recipient_gender"),
        gift_recipient_relation=state.get("gift_recipient_relation"),
        emotional_context=state.get("emotional_context"),
        rejected_products=rejected_products,
        image_context=state.get("image_context"),
        language=state.get("language", "english"),
        top_level_categories=categories
    )

    formatted_messages.insert(0, {
        "role": "system",
        "content": system_prompt
    })

    max_loops = 6
    loops = 0

    while loops < max_loops:
        if len(search_results) >= 8:
            break
        loops += 1
        try:
            response = await client.chat.completions.create(
                model=settings.model_shopper,
                messages=formatted_messages,
                tools=KAPRUKA_TOOL_SCHEMAS
            )

            message = response.choices[0].message
            formatted_messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (message.tool_calls or [])
                ] or None
            })

            if not message.tool_calls:
                break

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                my_steps.append({
                    "type": "thinking", "step": fn_name,
                    "detail": f"Executing {fn_name}...", "status": "running"
                })

                if fn_name in TOOL_MAP:
                    result = await TOOL_MAP[fn_name](**args)

                    if fn_name == "kapruka_search_products":
                        new_results = parse_search_results(result)
                        filtered = [r for r in new_results
                                    if r.get("product_id") not in rejected_products
                                    and is_relevant(r, intent_context)]
                        search_results.extend(filtered)
                    elif fn_name == "kapruka_get_product":
                        detail = parse_product_detail(result)
                        for p in search_results:
                            if p.get("product_id") == args.get("product_id"):
                                p["image_url"] = detail.get("image_url", "")
                                p["original_price"] = detail.get("original_price")
                                break
                else:
                    result = {"error": "Unknown tool"}

                my_steps[-1]["status"] = "done"

                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": json.dumps(result)
                })

        except Exception as e:
            logger.error(f"Shopper error: {e}")
            my_steps.append({
                "type": "thinking", "step": "shopper_error",
                "detail": "Failed to call tools", "status": "error"
            })
            break

    # Dedupe before the guaranteed image fetch pass
    search_results = dedupe_products(search_results)

    # GUARANTEED PASS — fetch images for any product still missing one,
    # regardless of whether the LLM's tool loop got to it.
    products_needing_detail = [
        p for p in search_results if not p.get("image_url")
    ][:7]

    if products_needing_detail:
        my_steps.append({
            "type": "thinking", "step": "kapruka_get_product",
            "detail": f"Fetching images for {len(products_needing_detail)} more items...",
            "status": "running"
        })

        for product in products_needing_detail:
            try:
                result = await kapruka_get_product(product_id=product["product_id"])
                detail = parse_product_detail(result)
                product["image_url"] = detail.get("image_url", "")
                product["original_price"] = detail.get("original_price")
            except Exception as e:
                logger.error(f"Failed to get detail for {product.get('product_id')}: {e}")

        my_steps[-1]["status"] = "done"

    return {
        "search_results": search_results,
        "thinking_steps": my_steps
    }