import json
import time
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.graph.state import AgentState
from app.services.llm import llm
from app.utils.ws_manager import send_agent_update
from app.utils.logging_config import logger
from app.services.database import update_workflow_run
from app.utils.text_helpers import ensure_text

async def run_planner(state: AgentState, config: RunnableConfig) -> dict:
    """
    Formulate the research objective and plan.
    Defends against type exceptions and logs state variable types.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Planner input - {key}: {type(val)}")

    query = ensure_text(state.get("query", ""))
    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    # Update workflow run state
    update_workflow_run(session_id, "Planner", "running")
    
    send_agent_update(session_id, "Planner", "running", "Planner: Constructing research strategy...")
    
    system_prompt = (
        "You are a research planner.\n"
        "Analyze the research query and return a strategy.\n"
        "You must return ONLY a JSON object containing exactly two keys:\n"
        "- 'goal': The core objective and scope.\n"
        "- 'plan': The search strategy.\n"
        "CRITICAL CONSTRAINT: The entire output (goal and plan combined) MUST be under 100 words. Be extremely concise.\n"
        "Do not include any text before or after the JSON."
    )
    
    human_prompt = f"Query: '{query}'"
    start_time = time.time()
    
    # Use 1.7b model for fast execution
    llm.model = "qwen3:1.7b"
    
    try:
        # 20s agent timeout protection
        response = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]),
            timeout=20.0
        )
        
        content = ensure_text(response.content).strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1]
                if content.startswith("json"):
                    content = content[4:]
        content = content.strip()
        
        data = json.loads(content)
        goal = ensure_text(data.get("goal", f"Analyze query: {query}"))
        plan = ensure_text(data.get("plan", f"1. Research key domains.\n2. Summarize findings."))
        
    except asyncio.TimeoutError:
        logger.error("Planner timed out after 20 seconds. Defaulting to fallback.")
        goal = f"Deconstruct and analyze the query: {query}"
        plan = f"1. Search vector DB and web.\n2. Aggregate findings."
    except Exception as e:
        logger.error(f"Planner error: {e}", exc_info=True)
        goal = f"Deconstruct and analyze the query: {query}"
        plan = f"1. Search vector DB and web.\n2. Aggregate findings."
        
    # Programmatic 100-word limit (converts to safe text beforehand)
    goal = ensure_text(goal)
    plan = ensure_text(plan)
    
    goal_words = goal.split()
    if len(goal_words) > 50:
        goal = " ".join(goal_words[:45]) + "..."
        
    plan_words = plan.split()
    if len(plan_words) > 50:
        plan = " ".join(plan_words[:45]) + "..."
        
    elapsed = time.time() - start_time
    log_msg = f"Planner: Strategy formulated in {elapsed:.2f}s."
    send_agent_update(session_id, "Planner", "completed", log_msg, elapsed=elapsed)
    
    return {
        "goal": goal,
        "plan": plan,
        "status": "Planner Completed",
        "execution_log": [f"Planner: Strategy formulated in {elapsed:.2f}s"]
    }
