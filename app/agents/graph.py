from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import GraphState
from app.agents.nodes.router import router_node
from app.agents.nodes.shopper import shopper_node
from app.agents.nodes.reflection import reflection_node
from app.agents.nodes.concierge import concierge_node
from app.agents.nodes.tracking import tracking_node
from app.agents.nodes.checkout import checkout_node


def route_after_reflection(state: GraphState) -> str:
    if state.get("reflection_needed"):
        return "shopper"
    return "concierge"


def route_after_router(state: GraphState) -> str:
    intent = state.get("intent", "search")
    if intent in ("greeting", "clarify", "order_confirmation"):
        return "concierge"
    if intent == "checkout":
        return "checkout"
    if intent == "track":
        return "tracking"
    # search, gift, delivery, budget, image_search → all go to shopper
    return "shopper"


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
