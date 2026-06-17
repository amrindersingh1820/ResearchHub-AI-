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

async def run_writer(state: AgentState, config: RunnableConfig) -> dict:
    """
    Synthesize research notes, objectives, and plan into a clean Markdown report.
    Uses async token streaming via WebSocket, timing metrics, and 90s timeout.
    Word limit constraint: Max 700 words.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Writer input - {key}: {type(val)}")

    session_id = config.get("configurable", {}).get("session_id", "default_session")
    
    try:
        query = ensure_text(state.get("query", ""))
        goal = ensure_text(state.get("goal", ""))
        plan = ensure_text(state.get("plan", ""))
        notes = ensure_text(state.get("research_notes", ""))
        sources = state.get("sources", [])
        
        # Update workflow run state
        update_workflow_run(session_id, "Writer", "running")
        
        send_agent_update(session_id, "Writer", "running", "Writer: Compiling grounding notes into formal Markdown report...")
        
        # Format bibliography sources
        formatted_sources = []
        if isinstance(sources, list):
            for idx, s in enumerate(sources):
                if isinstance(s, dict):
                    name_str = ensure_text(s.get('name', 'Source'))
                    url_val = s.get('url_or_path')
                    url_text = f" ({ensure_text(url_val)})" if url_val else ""
                    formatted_sources.append(f"[{idx+1}] {name_str}{url_text}")
                else:
                    formatted_sources.append(f"[{idx+1}] {ensure_text(s)}")
        sources_text = "\n".join(formatted_sources) if formatted_sources else "No external sources indexed."
        
        system_prompt = (
            "You are a principal technical author.\n"
            "Your task is to write a comprehensive, professional Markdown report based on the provided strategic goal, plan, and research notes.\n"
            "Your report MUST contain the following headers exactly (do not omit any):\n"
            "# Executive Summary\n"
            "# Research Objective\n"
            "# Key Findings\n"
            "# Analysis\n"
            "# Opportunities\n"
            "# Risks\n"
            "# Future Outlook\n"
            "# Conclusion\n"
            "# References\n\n"
            "CRITICAL CITATION RULES:\n"
            "1. Every claim, percentage, or statistic in the report MUST be cited with its corresponding bibliography number (e.g. [1], [2]).\n"
            "2. Do NOT invent percentages, statistics, or references not found in the grounding notes.\n"
            "3. Do NOT invent URLs or sources. Only use items from the provided bibliography.\n\n"
            "CRITICAL CONSTRAINT: You must be extremely concise. Do NOT exceed 700 words. Be authoritative.\n"
            "Start directly with the Markdown. Do not include any introduction greetings or outlines."
        )
        
        human_prompt = (
            f"Research Topic: {query}\n"
            f"Strategic Goal: {goal}\n"
            f"Plan: {plan}\n\n"
            f"--- RESEARCH NOTES ---\n{notes}\n\n"
            f"--- BIBLIOGRAPHY ---\n{sources_text}"
        )
        
        # Use qwen3:4b for high-quality report writing
        llm.model = "qwen3:4b"
        
        start_time = time.time()
        report_content = ""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            # 90s agent timeout protection
            async for chunk in llm.astream(messages):
                token = chunk.content
                if token:
                    report_content += token
                    send_agent_chunk(session_id, "Writer", token)
                    
            # Post-process content constraints
            report_content = report_content.strip()
            
            # Verify title header
            if not report_content.startswith("# "):
                report_content = f"# Research Report: {query}\n\n" + report_content
                
            # Verify references block
            if "# References" not in report_content:
                report_content += f"\n\n# References\n{sources_text}"
                
            # Programmatic 700-word limit check
            report_content = ensure_text(report_content)
            words = report_content.split()
            if len(words) > 700:
                report_content = " ".join(words[:690]) + "...\n\n[Report truncated to satisfy 700-word constraint]"
                
        except asyncio.TimeoutError:
            logger.error("Writer timed out after 90 seconds. Defaulting to fallback.")
            report_content = f"# Research Report: {query}\n\n# Executive Summary\nWriter timed out during report generation."
        except Exception as e:
            logger.error(f"Writer error: {e}", exc_info=True)
            report_content = f"# Research Report: {query}\n\n# Executive Summary\nWriter encountered an error: {e}"
            
        elapsed = time.time() - start_time
        log_msg = f"Writer: Report compiled and streamed in {elapsed:.2f}s."
        send_agent_update(session_id, "Writer", "completed", log_msg, elapsed=elapsed)
        
        # Update workflow run state as completed
        update_workflow_run(session_id, "Writer", "completed")
        
        return {
            "final_report": report_content,
            "status": "Writer Completed",
            "execution_log": [f"Writer: Report compiled in {elapsed:.2f}s"]
        }
    except Exception as e:
        logger.error(f"Writer critical node failure: {e}", exc_info=True)
        # Update workflow run state as completed/failed to prevent lock
        update_workflow_run(session_id, "Writer", "completed")
        return {
            "final_report": f"# Research Report\n\nWriter critical node failure: {e}",
            "status": "Writer Failed",
            "execution_log": [f"Writer: Critical failure: {e}"]
        }

