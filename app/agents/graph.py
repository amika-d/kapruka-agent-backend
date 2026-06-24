from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import GraphState
from app.agents.nodes.router import router_node
from app.agents.nodes.shopper import shopper_node
from app.agents.nodes.reflection import reflection_node
from app.agents.nodes.concierge import concierge_node

def route_after_reflection(state: GraphState) -> str:
    if state.get("reflection_needed"):
        return "shopper"
    return "concierge"


def route_after_router(state: GraphState) -> str:
    if state.get("intent") == "greeting":
        return "concierge"
    if state.get("intent") == "clarify":
        return "concierge" 
    return "shopper"

workflow = StateGraph(GraphState)

workflow.add_node("router", router_node)
workflow.add_node("shopper", shopper_node)
workflow.add_node("reflection", reflection_node)
workflow.add_node("concierge", concierge_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router)
workflow.add_edge("shopper", "reflection")
workflow.add_conditional_edges("reflection", route_after_reflection)
workflow.add_edge("concierge", END)

memory = MemorySaver()
compiled_graph = workflow.compile(checkpointer=memory)
