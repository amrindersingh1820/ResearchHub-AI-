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

async def run_coder(state: AgentState, config: RunnableConfig) -> dict:
    """
    Generate code directly based on user's query.
    Uses qwen3:4b with async token streaming, timing metrics, and 45s timeout.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Coder input - {key}: {type(val)}")

    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    try:
        query = ensure_text(state.get("query", ""))
        
        # Update workflow run state
        update_workflow_run(session_id, "Coder", "running")
        
        send_agent_update(session_id, "Coder", "running", "Coder: Generating code response...")
        
        system_prompt = (
            "You are an expert Coding Agent.\n"
            "Your task is to solve the programming request directly and output ONLY the source code.\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY the source code block. Do NOT include any explanations, introduction, markdown headers, executive summaries, or analysis.\n"
            "2. Keep the code clean, fully functional, and ready to use.\n"
            "3. Provide ONLY the raw code or the code inside a standard markdown code fence block (e.g. ```c ... ```) without any other wrapping text."
        )
        
        human_prompt = f"Coding request: '{query}'"
        
        # Use qwen3:4b for coding queries
        llm.model = "qwen3:4b"
        
        start_time = time.time()
        code_content = ""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            # 45s agent timeout protection
            async for chunk in llm.astream(messages):
                token = chunk.content
                if token:
                    code_content += token
                    send_agent_chunk(session_id, "Coder", token)
                    
        except asyncio.TimeoutError:
            logger.error("Coder timed out after 45 seconds.")
            code_content = "// Error: Coder timed out after 45s"
        except Exception as e:
            logger.error(f"Coder error: {e}", exc_info=True)
            code_content = f"// Error: Coder encountered exception: {e}"
            
        elapsed = time.time() - start_time
        log_msg = f"Coder: Code generated and streamed in {elapsed:.2f}s."
        send_agent_update(session_id, "Coder", "completed", log_msg, elapsed=elapsed)
        
        # Update workflow run state as completed
        update_workflow_run(session_id, "Coder", "completed")
        
        return {
            "final_report": code_content,
            "status": "Coder Completed",
            "execution_log": [f"Coder: Code compiled in {elapsed:.2f}s"]
        }
    except Exception as e:
        logger.error(f"Coder critical node failure: {e}", exc_info=True)
        # Update workflow run state as completed/failed to prevent lock
        update_workflow_run(session_id, "Coder", "completed")
        return {
            "final_report": f"// Coder critical node failure: {e}",
            "status": "Coder Failed",
            "execution_log": [f"Coder: Critical failure: {e}"]
        }

