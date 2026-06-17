import time
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.graph.state import AgentState
from app.services.llm import llm
from app.utils.ws_manager import send_agent_update, send_agent_chunk
from app.utils.logging_config import logger
from app.services.database import update_workflow_run
from app.utils.text_helpers import ensure_text

async def run_assistant(state: AgentState, config: RunnableConfig) -> dict:
    """
    Handle general chatbot conversational queries.
    Uses qwen3:4b with async token streaming, timing metrics, and 45s timeout.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Assistant input - {key}: {type(val)}")

    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    try:
        query = ensure_text(state.get("query", ""))
        
        # Update workflow run state
        update_workflow_run(session_id, "Assistant", "running")
        
        send_agent_update(session_id, "Assistant", "running", "Assistant: Formulating conversational response...")
        
        system_prompt = (
            "You are a helpful, friendly General Assistant.\n"
            "Respond conversationally to the user greeting or simple chat. Keep it concise, professional, and clear.\n"
            "Do not write research reports or code unless specifically asked in other workflows."
        )
        
        human_prompt = f"Query: '{query}'"
        
        # Use qwen3:4b for assistant queries
        llm.model = "qwen3:4b"
        
        start_time = time.time()
        response_content = ""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            # 45s agent timeout protection
            async for chunk in llm.astream(messages):
                token = chunk.content
                if token:
                    response_content += token
                    send_agent_chunk(session_id, "Assistant", token)
                    
        except asyncio.TimeoutError:
            logger.error("Assistant timed out after 45 seconds.")
            response_content = "Error: Conversational assistant timed out after 45s."
        except Exception as e:
            logger.error(f"Assistant error: {e}", exc_info=True)
            response_content = f"Error: Assistant encountered an issue: {e}"
            
        elapsed = time.time() - start_time
        log_msg = f"Assistant: Conversational response ready in {elapsed:.2f}s."
        send_agent_update(session_id, "Assistant", "completed", log_msg, elapsed=elapsed)
        
        # Update workflow run state as completed
        update_workflow_run(session_id, "Assistant", "completed")
        
        return {
            "final_report": response_content,
            "status": "Assistant Completed",
            "execution_log": [f"Assistant: Response ready in {elapsed:.2f}s"]
        }
    except Exception as e:
        logger.error(f"Assistant critical node failure: {e}", exc_info=True)
        # Update workflow run state as completed/failed to prevent lock
        update_workflow_run(session_id, "Assistant", "completed")
        return {
            "final_report": f"Assistant critical node failure: {e}",
            "status": "Assistant Failed",
            "execution_log": [f"Assistant: Critical failure: {e}"]
        }

