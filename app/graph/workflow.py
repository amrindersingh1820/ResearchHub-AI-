from langgraph.graph import StateGraph, START, END

from app.graph.state import AgentState
from app.agents.router import run_router
from app.agents.planner import run_planner
from app.agents.researcher import run_researcher
from app.agents.writer import run_writer
from app.agents.coder import run_coder
from app.agents.assistant import run_assistant
from app.agents.memory_context import run_memory_context
from app.utils.logging_config import logger

def route_intent(state: AgentState) -> str:
    """
    Conditional router edge based on query intent.
    """
    intent = state.get("intent", "research")
    if intent == "code":
        return "coder"
    elif intent == "general":
        return "assistant"
    elif intent == "follow_up":
        return "memory_context"
    else:
        return "planner"

def build_workflow():
    """
    Compile the stategraph representing the intent routing agent system.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("router", run_router)
    workflow.add_node("planner", run_planner)
    workflow.add_node("researcher", run_researcher)
    workflow.add_node("writer", run_writer)
    workflow.add_node("coder", run_coder)
    workflow.add_node("assistant", run_assistant)
    workflow.add_node("memory_context", run_memory_context)
    
    # Connect starting node
    workflow.add_edge(START, "router")
    
    # Add conditional branching from router
    workflow.add_conditional_edges(
        "router",
        route_intent,
        {
            "planner": "planner",
            "coder": "coder",
            "assistant": "assistant",
            "memory_context": "memory_context"
        }
    )
    
    # Connect research branch nodes in sequence
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", END)
    
    # Connect other branches directly to END
    workflow.add_edge("coder", END)
    workflow.add_edge("assistant", END)
    workflow.add_edge("memory_context", END)
    
    compiled_graph = workflow.compile()
    logger.info("LangGraph Intent Router workflow compiled successfully.")
    return compiled_graph

# Ready-to-use compiled graph
research_graph = build_workflow()
