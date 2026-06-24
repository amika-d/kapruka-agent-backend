from typing import TypedDict, Annotated, Optional, List, Dict, Any
import operator

def add_messages(left: list, right: list) -> list:
    return left + right

class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    language: str
    occasion: Optional[str]
    intent: Optional[str]
    budget_lkr: Optional[float]
    image_context: Optional[str]
    cart: List[Dict[str, Any]]
    delivery_city: Optional[str]
    delivery_date: Optional[str]
    gift_recipient_gender: Optional[str]
    gift_recipient_relation: Optional[str]
    emotional_context: Optional[str]
    search_results: List[Dict[str, Any]]
    reflection_needed: bool
    reflection_count: int
    thinking_steps: Annotated[List[Dict[str, Any]], operator.add]
    final_response: Optional[str]
