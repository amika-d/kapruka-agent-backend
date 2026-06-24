from typing import Literal, Optional
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    image_base64: Optional[str] = None
    timestamp: Optional[str] = None

class CartItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    image_url: str
    currency: str = "LKR"

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    cart: list[CartItem] = Field(default_factory=list)
    image_base64: Optional[str] = None

class ThinkingEvent(BaseModel):
    type: Literal["thinking"] = "thinking"
    step: str
    detail: str
    status: Literal["running", "done", "error"]

class ProductCard(BaseModel):
    product_id: str
    name: str
    price: float
    original_price: Optional[float] = None
    image_url: str
    url: str
    in_stock: bool
    currency: str
    variant: Optional[str] = None
    delivery_available: Optional[bool] = None
    delivery_price: Optional[float] = None

class DeliveryQuote(BaseModel):
    city: str
    date: str
    available: bool
    price_lkr: float
    perishable_warning: bool

class CheckoutRequest(BaseModel):
    cart: list[CartItem]
    recipient_name: str
    recipient_phone: str
    delivery_city: str
    delivery_date: str
    sender_name: str
    sender_email: str
    gift_message: Optional[str] = None
    currency: str = "LKR"

class CheckoutResponse(BaseModel):
    pay_url: str
    order_id: str
    expires_in_minutes: int = 60

class OrderStatus(BaseModel):
    order_number: str
    status: str
    recipient: str
    items: list
    timeline: list[dict]

class ChatResponse(BaseModel):
    session_id: str
    message: str
    products: list[ProductCard] = Field(default_factory=list)
    thinking_steps: list[ThinkingEvent] = Field(default_factory=list)
    delivery_quote: Optional[DeliveryQuote] = None
    cart_action: Optional[dict] = None
