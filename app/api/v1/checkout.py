from app.agents import state
from app.core.database import get_session_store
import re
import json
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from openai import AsyncOpenAI

from app.mcp.tools import (
    kapruka_list_delivery_cities,
    kapruka_create_order,
)
from app.core.cart_validator import validate_cart
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

_llm = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CheckoutCartItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    image_url: str = ""
    currency: str = "LKR"


class CheckoutPayload(BaseModel):
    cart: list[CheckoutCartItem]
    recipient_name: str
    recipient_phone: str
    delivery_city: str          # raw user input — will be resolved
    delivery_address: str = ""
    delivery_date: str          # YYYY-MM-DD
    gift_message: Optional[str] = None
    session_id: str = "checkout"
    currency: str = "LKR"


class CheckoutResult(BaseModel):
    order_number: Optional[str]
    total: Optional[float]
    pay_link: Optional[str]
    expires_at: Optional[str]
    issues: list[str]
    resolved_city: Optional[str]


class GiftMessageRequest(BaseModel):
    occasion: str
    vibe: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_cities(raw: dict) -> list[str]:
    """Extract canonical city names from kapruka_list_delivery_cities response."""
    text = raw.get("result", "")
    cities = []
    for line in text.splitlines():
        line = line.strip().lstrip("-•* ").strip()
        # Lines usually look like: "Colombo 05" or "- Colombo 05 | ..."
        if line and not line.startswith("#"):
            # Take only the city name part (before | or URL)
            city = re.split(r"\s*[\|–—]", line)[0].strip()
            if city:
                cities.append(city)
    return cities[:50]


def _parse_order_result(raw: dict) -> dict:
    """Extract order_number, total, pay_link, expires_at from create_order result."""
    text = raw.get("result", "")
    out: dict = {"order_number": None, "total": None, "pay_link": None, "expires_at": None}

    # Pay link
    url_match = re.search(r"(https?://\S+)", text)
    if url_match:
        out["pay_link"] = url_match.group(1).rstrip(")")

    # Order number
    num_match = re.search(r"(?:order[_ ](?:number|no|id)[:\s#]*|#)([A-Z0-9\-]{6,})", text, re.I)
    if num_match:
        out["order_number"] = num_match.group(1)

    # Total
    total_match = re.search(r"(?:total|amount)[:\s]*(?:LKR\s*)?([\d,]+(?:\.\d+)?)", text, re.I)
    if total_match:
        try:
            out["total"] = float(total_match.group(1).replace(",", ""))
        except ValueError:
            pass

    return out


async def _resolve_city(raw_city: str) -> Optional[str]:
    """Call kapruka_list_delivery_cities and find the best canonical match."""
    try:
        result = await kapruka_list_delivery_cities(query=raw_city, limit=10)
        cities = _parse_cities(result)
        if not cities:
            return None
        raw_lower = raw_city.lower()
        for city in cities:
            if raw_lower in city.lower() or city.lower().startswith(raw_lower):
                return city
        return cities[0]  # best available
    except Exception as e:
        logger.warning(f"City resolution failed: {e}")
        return None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/cities")
async def search_cities(query: str = Query(..., min_length=2)):
    """Typeahead endpoint — returns matched canonical city names."""
    try:
        raw = await kapruka_list_delivery_cities(query=query, limit=15)
        cities = _parse_cities(raw)
        return {"cities": cities}
    except Exception as e:
        logger.error(f"City search error: {e}")
        raise HTTPException(status_code=500, detail="City search failed")


@router.post("/checkout")
async def create_checkout(payload: CheckoutPayload) -> CheckoutResult:
    """
    1. Resolve delivery city
    2. Validate cart (stock + price)
    3. Create order via Kapruka MCP
    4. Return order_number, pay_link, total, expires_at
    """

    # ── 1. Resolve city ───────────────────────────────────────────────────────
    resolved_city = await _resolve_city(payload.delivery_city)
    if not resolved_city:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve delivery city '{payload.delivery_city}'. "
                   "Please use the city search to pick an exact match."
        )

    # ── 2. Validate cart ──────────────────────────────────────────────────────
    cart_dicts = [item.model_dump() for item in payload.cart]
    validation = await validate_cart(cart_dicts)

    if not validation["items"]:
        raise HTTPException(
            status_code=400,
            detail={"message": "No valid items in cart", "issues": validation["issues"]}
        )

    # ── 3. Create order ───────────────────────────────────────────────────────
    try:
        result = await kapruka_create_order(
            cart=[
                {"product_id": i["product_id"], "quantity": i.get("quantity", 1)}
                for i in validation["items"]
            ],
            recipient={"name": payload.recipient_name, "phone": payload.recipient_phone},
            delivery={"city": resolved_city, "date": payload.delivery_date, "address": payload.delivery_address},
            sender={"name": "Kiyanna User", "email": "kiyanna@kapruka.com"},
            gift_message=payload.gift_message,
            currency=payload.currency,
        )
        
    except Exception as e:
        logger.error(f"create_order failed: {e}")
        raise HTTPException(status_code=502, detail="Order creation failed — try again")

    parsed = _parse_order_result(result)
    db = get_session_store()
    session = db.get_session(payload.session_id)
    session["last_order_number"] = [parsed["order_number"]]
    session["order_history"] = session.get("order_history", []) + [parsed["order_number"]]

    return CheckoutResult(
        order_number=parsed["order_number"],
        total=parsed["total"],
        pay_link=parsed["pay_link"],
        expires_at=parsed["expires_at"],
        issues=validation["issues"],
        resolved_city=resolved_city,
    )


@router.post("/gift-message-suggest")
async def suggest_gift_message(body: GiftMessageRequest):
    """Quick Haiku call to generate a warm gift message suggestion."""
    try:
        prompt = (
            f"Write a short, warm gift message (2-3 sentences max) for a Kapruka order.\n"
            f"Occasion: {body.occasion}\n"
            f"Vibe/tone: {body.vibe}\n"
            f"Write ONLY the message itself. No preamble. No quotes around it."
        )
        response = await _llm.chat.completions.create(
            model=settings.model_router,   # haiku — fast and cheap
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        suggestion = response.choices[0].message.content.strip()
        return {"suggestion": suggestion}
    except Exception as e:
        logger.error(f"Gift message suggest failed: {e}")
        raise HTTPException(status_code=500, detail="Suggestion failed")
