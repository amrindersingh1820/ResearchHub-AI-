import json
import time
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.graph.state import AgentState
from app.services.llm import llm
from app.services.vector_store import similarity_search
from app.services.tools import get_web_search_provider
from app.utils.ws_manager import send_agent_update
from app.utils.logging_config import logger
from app.services.database import update_workflow_run, get_cached_val, set_cached_val

import json
import time
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.graph.state import AgentState
from app.services.llm import llm
from app.services.vector_store import similarity_search
from app.services.tools import get_web_search_provider
from app.utils.ws_manager import send_agent_update
from app.utils.logging_config import logger
from app.services.database import update_workflow_run, get_cached_val, set_cached_val
from app.utils.text_helpers import ensure_text

async def async_similarity_search(query: str, session_id: str) -> list:
    """Async wrapper for ChromaDB vector search."""
    return await asyncio.to_thread(similarity_search, query, session_id=session_id, k=4)

async def async_web_search(web_provider, query: str) -> list:
    """Async wrapper for Web search provider."""
    return await asyncio.to_thread(web_provider.search, query, limit=3)

async def run_researcher(state: AgentState, config: RunnableConfig) -> dict:
    """
    Execute RAG search and Web queries concurrently, then compile grounded research notes.
    Uses asyncio.gather() for parallel execution, caches results, and runs under 60s timeout.
    Word limit constraint: Max 300 words.
    """
    # 6. Type-safe logging
    for key, val in state.items():
        logger.info(f"[State Type Audit] Researcher input - {key}: {type(val)}")
        
    session_id = config.get("configurable", {}).get("session_id", "default_session")
    query = ensure_text(state.get("query", ""))
    
    try:
        # Update workflow run state
        update_workflow_run(session_id, "Researcher", "running")
        
        send_agent_update(session_id, "Researcher", "running", "Researcher: Gathering grounding data concurrently...")
        
        start_time = time.time()
        
        # Check SQLite cache for grounding context first
        cache_key = f"grounding_context:{query}:{session_id}"
        cached_results = get_cached_val(cache_key)
        
        if cached_results:
            logger.info(f"Researcher: Retrieved cached grounding data for query '{query}'")
            db_context = cached_results.get("db_context", [])
            db_sources = cached_results.get("db_sources", [])
            web_context = cached_results.get("web_context", [])
            web_sources = cached_results.get("web_sources", [])
        else:
            # Run ChromaDB Vector Search and Web Search concurrently
            web_provider = get_web_search_provider()
            
            try:
                # 60s agent timeout protection
                db_results, web_results = await asyncio.wait_for(
                    asyncio.gather(
                        async_similarity_search(query, session_id),
                        async_web_search(web_provider, query)
                    ),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                logger.error("Researcher timed out after 60 seconds. Continuing with empty context.")
                db_results, web_results = [], []
            except Exception as e:
                logger.error(f"Researcher grounding failed: {e}", exc_info=True)
                db_results, web_results = [], []
                
            # Parse ChromaDB results
            db_context = []
            db_sources = []
            for doc in db_results:
                if doc is None:
                    continue
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {}) or {}
                    fname = meta.get("file_name", "Uploaded Document")
                    content = doc.get("content", "")
                elif hasattr(doc, "page_content"):
                    meta = getattr(doc, "metadata", {}) or {}
                    fname = meta.get("file_name", "Uploaded Document")
                    content = doc.page_content
                else:
                    fname = "Uploaded Document"
                    content = str(doc)
                
                content_str = ensure_text(content)
                fname_str = ensure_text(fname)
                db_context.append(f"[Document: {fname_str}] {content_str}")
                db_sources.append({
                    "name": f"Document: {fname_str}",
                    "type": "pdf",
                    "url_or_path": fname_str,
                    "snippet": content_str[:200]
                })
                
            # Parse Web Search results
            web_context = []
            web_sources = []
            for doc in web_results:
                if doc is None:
                    continue
                if isinstance(doc, dict):
                    title = doc.get("title", "Web Result")
                    content = doc.get("content", "")
                    url = doc.get("url", "")
                elif hasattr(doc, "page_content"):
                    title = getattr(doc, "metadata", {}).get("title", "Web Result")
                    content = doc.page_content
                    url = getattr(doc, "metadata", {}).get("url", "")
                else:
                    title = "Web Result"
                    content = str(doc)
                    url = ""
                
                title_str = ensure_text(title)
                content_str = ensure_text(content)
                url_str = ensure_text(url)
                web_context.append(f"[Web Source: {title_str}] {content_str}")
                web_sources.append({
                    "name": title_str,
                    "type": "web",
                    "url_or_path": url_str,
                    "snippet": content_str[:200]
                })
                
            # Save to SQLite cache
            set_cached_val(cache_key, {
                "db_context": db_context,
                "db_sources": db_sources,
                "web_context": web_context,
                "web_sources": web_sources
            }, ttl_seconds=1800) # cache for 30 minutes
            
        combined_context = "\n\n".join(db_context + web_context)
        all_sources = db_sources + web_sources
        
        if not combined_context:
            combined_context = "No RAG or Web documents were found for this query. Perform a baseline analysis."
            
        system_prompt = (
            "You are an expert technical researcher.\n"
            "Your task is to analyze the query and the provided context, and compile raw research notes.\n"
            "Generate:\n"
            "- Key findings\n"
            "- Supporting evidence\n"
            "- Crucial technical analysis\n\n"
            "CRITICAL GROUNDING RULES:\n"
            "1. Stay strictly grounded in the provided context (ChromaDB Results and Web Search Results) only.\n"
            "2. Do NOT invent enterprise statistics, percentages, or references that do not exist in the context.\n"
            "3. If information is not in the context, state that it is unavailable.\n\n"
            "CRITICAL CONSTRAINT: You must be extremely concise. Do not exceed 300 words. Keep it structured.\n"
            "Do not include preamble or greeting. Ground all statements in the context."
        )
        
        human_prompt = (
            f"Research Topic: {query}\n\n"
            f"--- GROUNDING CONTEXT ---\n{combined_context}\n"
        )
        
        # Researcher notes compile model
        llm.model = "qwen3:4b"
        
        try:
            response = await asyncio.wait_for(
                llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]),
                timeout=30.0
            )
            research_notes = ensure_text(response.content).strip()
        except Exception as e:
            logger.error(f"Researcher notes compilation failed: {e}")
            research_notes = f"Baseline research notes on: {query}.\n- Current state focuses on digital transformation.\n- Evidence points to automated workflow integration."
    
        # Programmatic 300-word limit check
        words = research_notes.split()
        if len(words) > 300:
            research_notes = " ".join(words[:290]) + "...\n[Notes truncated to satisfy 300-word constraint]"
            
        elapsed = time.time() - start_time
        log_msg = f"Researcher: Notes compiled. Sources registered: {len(all_sources)} in {elapsed:.2f}s."
        send_agent_update(session_id, "Researcher", "completed", log_msg, elapsed=elapsed)
        
        return {
            "research_notes": research_notes,
            "sources": all_sources,
            "retrieved_chunks": db_context[:3],
            "status": "Researcher Completed",
            "execution_log": [f"Researcher: Notes compiled in {elapsed:.2f}s"]
        }
    except Exception as e:
        logger.error(f"Researcher critical node failure: {e}", exc_info=True)
        return {
            "research_notes": f"Research node failed. Defaulting to query: {query}",
            "sources": [],
            "retrieved_chunks": [],
            "status": "Researcher Failed",
            "execution_log": [f"Researcher: Critical failure: {e}"]
        }

