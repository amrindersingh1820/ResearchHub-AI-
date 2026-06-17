import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.graph.state import AgentState
from app.services.llm import get_llm
from app.utils.ws_manager import send_agent_update
from app.utils.logging_config import logger

def run_coordinator(state: AgentState, config: RunnableConfig) -> dict:
    """
    Decompose the research goal into 3-5 target topics.
    """
    query = state["query"]
    goal = state["goal"]
    plan = state["plan"]
    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    send_agent_update(session_id, "Coordinator", "running", "Coordinator: Extracting target topics from strategic plan...")
    
    system_prompt = (
        "You are a professional research coordinator.\n"
        "Your task is to analyze the research query, goal, and strategy, and break it down into exactly 3 to 5 discrete, highly focused research topics.\n"
        "These topics must cover the scope of the goal without overlap.\n"
        "You must return ONLY a JSON object with a single key 'topics' containing a list of strings.\n"
        "Example:\n"
        '{\n  "topics": ["Overview of AI in Cybersecurity", "Current Threats and Vulnerabilities", "Future Trends and Mitigations"]\n}\n'
        "Do not include any explanation or markdown wrappers outside the JSON."
    )
    
    human_prompt = (
        f"Query: {query}\n"
        f"Goal: {goal}\n"
        f"Plan: {plan}\n\n"
        "Extract 3-5 focused topics."
    )
    
    try:
        llm = get_llm(json_mode=True, temperature=0.1)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        
        content = response.content.strip()
        data = json.loads(content)
        topics = data.get("topics", [])
        
        # Validation
        if not isinstance(topics, list) or len(topics) < 2:
            raise ValueError("Invalid topics structure returned by LLM")
            
        topics = topics[:5]
        
        log_message = f"Extracted research domains: {', '.join(topics)}"
        send_agent_update(session_id, "Coordinator", "completed", f"Coordinator: {log_message}")
        
        return {
            "topics": topics,
            "agent_status": "Coordinator Completed",
            "execution_log": [f"Coordinator: {log_message}"]
        }
    except Exception as e:
        logger.error(f"Coordinator Agent error: {e}", exc_info=True)
        fallback_topics = [
            f"Core definitions and current state of {query}",
            f"Key opportunities and applications of {query}",
            f"Critical risks, challenges, and future trends of {query}"
        ]
        
        send_agent_update(session_id, "Coordinator", "completed", f"Coordinator (fallback): Selected {len(fallback_topics)} core tracks.")
        
        return {
            "topics": fallback_topics,
            "agent_status": "Coordinator Completed (with fallback)",
            "execution_log": [f"Coordinator Error: Failed to extract topics. Using fallback. Error: {e}"]
        }
