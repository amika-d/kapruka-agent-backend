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
    """Extract canonical city names from kapruka_list_delivery_cities response.
    
    Kapruka returns lines like:
      - **Colombo 01**  _aliases: Colombo1_
    We want only the text between **...**.
    """
    text = raw.get("result", "")
    # Primary: extract all **City Name** fragments
    cities = re.findall(r'\*\*([^*]+)\*\*', text)
    cities = [c.strip() for c in cities if c.strip()]
    if cities:
        return cities[:50]
    # Fallback: plain lines (no bold markdown)
    result = []
    for line in text.splitlines():
        line = line.strip().lstrip("-•* ").strip()
        if line and not line.startswith("#"):
            city = re.split(r"\s*[\|\u2013\u2014]", line)[0].strip()
            if city:
                result.append(city)
    return result[:50]


def _parse_order_result(raw: dict) -> dict:
    text = raw.get("result", "")
    out: dict = {"order_number": None, "total": None, "pay_link": None, "expires_at": None}

    num_match = re.search(r'Order created — `([^`]+)`', text)
    if num_match:
        out["order_number"] = num_match.group(1)

    total_match = re.search(r'\*\*Grand total:\*\*\s*LKR\s*([\d,]+)', text)
    if total_match:
        out["total"] = float(total_match.group(1).replace(",", ""))

    pay_match = re.search(r'\[Open checkout to pay\]\((https?://[^)]+)\)', text)
    if pay_match:
        out["pay_link"] = pay_match.group(1)

    expiry_match = re.search(r'expires at ([\d\-T:+]+)', text)
    if expiry_match:
        out["expires_at"] = expiry_match.group(1)

    return out


async def _resolve_city(raw_city: str) -> Optional[str]:
    """Resolve a raw user city string to the canonical Kapruka city name.
    
    Kapruka returns markdown like: - **Colombo 01**  _aliases: Colombo1_
    We extract only the content between **...**.
    """
    try:
        result = await kapruka_list_delivery_cities(query=raw_city, limit=10)
        text = result.get("result", "")

        # Extract all **City Name** values — these are the canonical names
        bold_cities = re.findall(r'\*\*([^*]+)\*\*', text)
        bold_cities = [c.strip() for c in bold_cities if c.strip()]

        if not bold_cities:
            # Fallback: use _parse_cities plain parser
            bold_cities = _parse_cities(result)

        if not bold_cities:
            return None

        # Best match: city name that starts with the user's input
        raw_lower = raw_city.lower()
        for city in bold_cities:
            if city.lower().startswith(raw_lower) or raw_lower in city.lower():
                return city

        # No close match — return first result
        return bold_cities[0]

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
            sender={"name": "Kiyanna User",},
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
