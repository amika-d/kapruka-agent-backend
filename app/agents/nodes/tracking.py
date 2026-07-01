import re 
from app.agents.state import GraphState
from app.mcp.tools import kapruka_track_order, parse_order_status

async def tracking_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    latest = messages[-1]["content"] if messages else ""
    
    order_match = re.search(r'\b([A-Z0-9]{8,})\b', latest.upper())
    
    if not order_match:
        return {
            "intent": "track_need_order_number",
            "thinking_steps": [{"type": "thinking", "step": "Tracking",
                "detail": "Need order number", "status": "done"}]
        }
    
    order_number = order_match.group(1)
    result = await kapruka_track_order(order_number=order_number)
    status = parse_order_status(result)
    
    return {
        "order_status": status,
        "thinking_steps": [{"type": "thinking", "step": "kapruka_track_order",
            "detail": f"Found order {status.get('order_number')}", "status": "done"}]
    }