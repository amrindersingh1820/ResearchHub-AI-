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

async def run_router(state: AgentState, config: RunnableConfig) -> dict:
    """
    Classify the user query intent.
    Defends against type exceptions and logs state variable types.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Router input - {key}: {type(val)}")

    query = ensure_text(state.get("query", ""))
    session_id = config.get("configurable", {}).get("session_id", "default_session")
    chat_history = state.get("chat_history", [])
    
    # Update workflow run state
    update_workflow_run(session_id, "Router", "running")
    
    send_agent_update(session_id, "Router", "running", "Router: Analyzing query intent...")
    
    # Build history context safely (Issue 5 & 11)
    history_context = ""
    if isinstance(chat_history, list):
        for msg in chat_history[:-1]:
            if isinstance(msg, dict):
                role = ensure_text(msg.get("role", "user")).upper()
                content = ensure_text(msg.get("content", ""))
                history_context += f"{role}: {content}\n"
            else:
                history_context += f"{ensure_text(msg)}\n"
    else:
        history_context = ensure_text(chat_history)

    system_prompt = (
        "You are an Intent Router. Your task is to classify the user query into one of these intents:\n"
        "1. 'follow_up': If the query is a follow-up instruction or question about the previous conversation or the generated report. Examples: 'expand the risks section', 'summarize this report', 'make it beginner friendly', 'explain section 3', 'what does this mean?'.\n"
        "2. 'research': For a brand new topic or analysis that requires building a research strategy, planning, gathering web search / PDF sources, and writing a report. Examples: 'Research AI in Healthcare', 'Future of Quantum Computing'.\n"
        "3. 'code': For tasks requesting code generation, debugging, syntax errors, or writing software components from scratch. Examples: 'Write a basic C program', 'Create a linked list in C++'.\n"
        "4. 'general': For simple chats, greetings, or conversational questions. Examples: 'Hello', 'Who are you'.\n\n"
        "You must output ONLY a valid JSON object containing exactly one key:\n"
        "- 'intent': must be exactly one of: 'research', 'code', 'general', 'follow_up'.\n"
        "Do not include any explanation or markdown formatting before or after the JSON."
    )
    
    human_prompt = f"Chat History:\n{history_context}\nNew Query: '{query}'"
    
    start_time = time.time()
    intent = "research" # default
    
    # Dynamically select 1.7b model for fast classification
    llm.model = "qwen3:1.7b"
    
    try:
        # 10s agent timeout protection
        response = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]),
            timeout=10.0
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
        intent = data.get("intent", "").lower().strip()
        if intent not in ["research", "code", "general", "follow_up"]:
            raise ValueError(f"Invalid intent: {intent}")
            
    except asyncio.TimeoutError:
        logger.error("Router timed out after 10 seconds. Defaulting to fallback.")
        intent = "research"
    except Exception as e:
        logger.error(f"Router error: {e}", exc_info=True)
        # Fallback keyword matching
        lower_q = query.lower()
        if chat_history and len(chat_history) > 1:
            intent = "follow_up"
        elif any(k in lower_q for k in ["code", "program", "function", "class", "error", "script", "c++", "python", "java", "react", "html"]):
            intent = "code"
        elif any(k in lower_q for k in ["hello", "hi", "who are you", "how are you", "hey"]):
            intent = "general"
        else:
            intent = "research"
            
    elapsed = time.time() - start_time
    log_msg = f"Router: Query classified as '{intent}' in {elapsed:.2f}s."
    send_agent_update(session_id, "Router", "completed", log_msg, elapsed=elapsed)
    
    return {
        "intent": intent,
        "status": f"Router Classified as {intent}",
        "execution_log": [f"Router: Classified intent as '{intent}' in {elapsed:.2f}s"]
    }
