from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import GraphState
from app.agents.nodes.router import router_node
from app.agents.nodes.shopper import shopper_node
from app.agents.nodes.reflection import reflection_node
from app.agents.nodes.concierge import concierge_node
from app.agents.nodes.tracking import tracking_node
import logging
from app.agents.nodes.checkout import checkout_node

logger = logging.getLogger(__name__)


def route_after_reflection(state: GraphState) -> str:
    dest = "shopper" if state.get("reflection_needed") else "concierge"
    logger.info(f"🔀 [ROUTING] route_after_reflection -> Routing to '{dest}'")
    return dest


def route_after_router(state: GraphState) -> str:
    intent = state.get("intent", "search")
    if intent in ("greeting", "clarify", "order_confirmation"):
        dest = "concierge"
    elif intent == "checkout":
        dest = "checkout"
    elif intent == "track":
        dest = "tracking"
    else:
        dest = "shopper"
    logger.info(f"🔀 [ROUTING] route_after_router (intent='{intent}') -> Routing to '{dest}'")
    return dest


workflow = StateGraph(GraphState)

workflow.add_node("router", router_node)
workflow.add_node("shopper", shopper_node)
workflow.add_node("reflection", reflection_node)
workflow.add_node("concierge", concierge_node)
workflow.add_node("tracking", tracking_node)
workflow.add_node("checkout", checkout_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router)
workflow.add_edge("shopper", "reflection")
workflow.add_conditional_edges("reflection", route_after_reflection)

workflow.add_edge("tracking", "concierge")
workflow.add_edge("checkout", "concierge")
workflow.add_edge("concierge", END)

memory = MemorySaver()
compiled_graph = workflow.compile(checkpointer=memory)
