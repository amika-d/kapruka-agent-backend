import re
from app.agents.state import GraphState
from app.mcp.tools import kapruka_create_order
from app.core.cart_validator import validate_cart


def parse_order_result(raw: dict) -> str | None:
    """Extract the payment URL from kapruka_create_order response."""
    text = raw.get("result", "")
    # Try to find a direct URL
    url_match = re.search(r'(https?://\S+)', text)
    if url_match:
        return url_match.group(1).rstrip(")")
    return None


async def checkout_node(state: GraphState) -> dict:
    cart = state.get("cart", [])
    delivery_city = state.get("delivery_city")
    delivery_date = state.get("delivery_date")

    # ── 1. Collect what's missing ────────────────────────────────────────────
    missing = []
    if not cart:
        missing.append("items in your cart")
    if not delivery_city:
        missing.append("delivery city")

    if missing:
        return {
            "intent": "checkout_incomplete",
            "thinking_steps": [{
                "type": "thinking",
                "step": "Checkout",
                "detail": f"Missing: {', '.join(missing)}",
                "status": "done"
            }]
        }

    # ── 2. Validate cart against live Kapruka data ───────────────────────────
    validation = await validate_cart(cart)

    if validation["issues"] and not validation["items"]:
        # Every item failed — abort
        return {
            "intent": "checkout_issues",
            "cart_issues": validation["issues"],
            "thinking_steps": [{
                "type": "thinking",
                "step": "Cart Validation",
                "detail": f"{len(validation['issues'])} issue(s) found",
                "status": "error"
            }]
        }

    # ── 3. Create the order ──────────────────────────────────────────────────
    recipient = state.get("recipient") or {"name": "Guest", "phone": ""}
    sender = state.get("sender") or {"name": "Kiyanna User", "email": ""}

    result = await kapruka_create_order(
        cart=[{"product_id": i["product_id"], "quantity": i.get("quantity", 1)} for i in validation["items"]],
        recipient=recipient,
        delivery={
            "city": delivery_city,
            "date": delivery_date or "",
        },
        sender=sender,
        gift_message=state.get("gift_message"),
    )

    pay_link = parse_order_result(result)

    thinking = [{
        "type": "thinking",
        "step": "kapruka_create_order",
        "detail": f"Order created → {pay_link or 'no URL returned'}",
        "status": "done"
    }]

    if validation["issues"]:
        thinking.append({
            "type": "thinking",
            "step": "Cart Warnings",
            "detail": "; ".join(validation["issues"]),
            "status": "done"
        })

    return {
        "final_response": None,   # concierge will phrase the confirmation
        "pay_link": pay_link,
        "cart_issues": validation["issues"] or None,
        "thinking_steps": thinking,
        "has_confirmed_order": True,
    }
