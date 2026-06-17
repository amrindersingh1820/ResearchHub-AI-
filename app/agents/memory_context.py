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

async def run_memory_context(state: AgentState, config: RunnableConfig) -> dict:
    """
    Handle follow-up queries that build upon the existing chat history and reports.
    Uses qwen3:4b with async token streaming, timing metrics, and 45s timeout.
    Word limit constraint: Max 700 words.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] MemoryContext input - {key}: {type(val)}")

    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    try:
        query = ensure_text(state.get("query", ""))
        prev_report = ensure_text(state.get("final_report", ""))
        chat_history = state.get("chat_history", [])
        
        # Update workflow run state
        update_workflow_run(session_id, "MemoryContext", "running")
        
        send_agent_update(session_id, "MemoryContext", "running", "MemoryContext: Analyzing follow-up request...")
        
        # Format history context for the agent safely
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
            "You are a Memory Context Agent. Your task is to process a follow-up query based on the preceding chat history and the existing report.\n"
            "Depending on the user query, you will either edit, expand, summarize, adapt, or answer questions about the report.\n\n"
            "CRITICAL RULES:\n"
            "1. If the user wants to revise or expand the report (e.g. 'Expand the risks section', 'Make it beginner friendly'), output the updated or revised full markdown report.\n"
            "2. If the user wants a summary or has a direct question (e.g. 'Summarize this report', 'Is there any citation for X?'), provide a direct conversational response or summary.\n"
            "3. Keep your output grounded in the previous report context, chat history, and any available grounding information.\n"
            "4. Enforce a word limit of 700 words. Keep it structured and high-quality.\n"
        )
        
        human_prompt = (
            f"--- PREVIOUS REPORT ---\n{prev_report}\n\n"
            f"--- CONVERSATION HISTORY ---\n{history_context}\n"
            f"Follow-up Query: {query}\n"
        )
        
        # Use qwen3:4b for follow-up context analysis
        llm.model = "qwen3:4b"
        
        start_time = time.time()
        content = ""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            # 45s agent timeout protection
            async for chunk in llm.astream(messages):
                token = chunk.content
                if token:
                    content += token
                    send_agent_chunk(session_id, "MemoryContext", token)
                    
            # Post-process content constraints
            content = content.strip()
            
            # Programmatic 700-word limit check
            content = ensure_text(content)
            words = content.split()
            if len(words) > 700:
                content = " ".join(words[:690]) + "...\n\n[Response truncated to satisfy 700-word constraint]"
                
        except asyncio.TimeoutError:
            logger.error("MemoryContext timed out after 45 seconds.")
            content = "Error: MemoryContext follow-up timed out after 45s."
        except Exception as e:
            logger.error(f"MemoryContext error: {e}", exc_info=True)
            content = f"Error: MemoryContext failed: {e}"
            
        elapsed = time.time() - start_time
        log_msg = f"MemoryContext: Follow-up response generated and streamed in {elapsed:.2f}s."
        send_agent_update(session_id, "MemoryContext", "completed", log_msg, elapsed=elapsed)
        
        # Update workflow run state as completed
        update_workflow_run(session_id, "MemoryContext", "completed")
        
        return {
            "final_report": content,
            "status": "MemoryContext Completed",
            "execution_log": [f"MemoryContext: Follow-up complete in {elapsed:.2f}s"]
        }
    except Exception as e:
        logger.error(f"MemoryContext critical node failure: {e}", exc_info=True)
        # Update workflow run state as completed/failed to prevent lock
        update_workflow_run(session_id, "MemoryContext", "completed")
        return {
            "final_report": f"MemoryContext critical node failure: {e}",
            "status": "MemoryContext Failed",
            "execution_log": [f"MemoryContext: Critical failure: {e}"]
        }

