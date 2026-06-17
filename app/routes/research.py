import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from app.models.schemas import ResearchRequest, ResearchResponse
from app.graph.workflow import research_graph
from app.services.database import (
    create_session, update_session, get_session,
    add_chat_message, get_chat_messages,
    create_workflow_run, update_workflow_run, add_report
)
from app.utils.ws_manager import ws_manager, send_agent_update
from app.utils.logging_config import logger
from typing import Optional

router = APIRouter(tags=["Research Agent Engine"])

@router.post("/research")
async def run_research_job(payload: ResearchRequest):
    """
    Submit a research topic. Executing the 3-agent LangGraph workflow
    synchronously for this HTTP request, while broadcasting state changes to WebSockets.
    Saves conversation history to SQLite and supports follow-up messaging.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    session_id = payload.session_id or str(uuid.uuid4())
    logger.info(f"Research Route: Starting session {session_id} for query '{query}'")
    
    # 1. Initialize SQLite session if new, otherwise load history
    existing_session = get_session(session_id)
    if not existing_session:
        try:
            create_session(session_id, query)
        except Exception as e:
            logger.error(f"Failed to create session in DB: {e}")
            raise HTTPException(status_code=500, detail="Database error occurred.")
    
    # 2. Append new user message to conversation history
    add_chat_message(session_id, "user", query)
    
    # 3. Retrieve prior chat history and existing reports
    chat_history = get_chat_messages(session_id)
    existing_report = existing_session.get("report", "") if existing_session else ""
    
    # 4. Initialize workflow run tracker in DB
    run_id = str(uuid.uuid4())
    create_workflow_run(run_id, session_id, "Router", "running")
    
    # 5. Setup initial state
    initial_state = {
        "query": query,
        "intent": "",
        "goal": "",
        "plan": "",
        "sources": [],
        "retrieved_chunks": [],
        "research_notes": "",
        "final_report": existing_report,  # Pre-populate context for follow-up runs
        "session_id": session_id,
        "status": "Started",
        "execution_log": [f"System: Starting routing pipeline for '{query}'."],
        "chat_history": chat_history
    }
    
    config = {"configurable": {"session_id": session_id}}
    
    try:
        send_agent_update(session_id, "System", "running", "System: Initializing agent graph workflow...")
        
        # Run graph execution
        final_state = await research_graph.ainvoke(initial_state, config=config)
        
        # 6. Read outcomes
        report = final_state.get("final_report", "")
        intent = final_state.get("intent", "research")
        goal = final_state.get("goal", "")
        plan = final_state.get("plan", "")
        sources = final_state.get("sources", [])
        research_notes = final_state.get("research_notes", "")
        
        # 7. Append assistant response to chat message thread
        add_chat_message(session_id, "assistant", report)
        
        # 8. Save report and metadata to DB
        add_report(session_id, str(uuid.uuid4()), report)
        update_session(
            session_id=session_id,
            intent=intent,
            goal=goal,
            plan=plan,
            sources=sources,
            research_notes=research_notes,
            report=report
        )
        
        # Mark workflow run completed in DB
        update_workflow_run(session_id, "Writer", "completed")
        
        send_agent_update(session_id, "System", "completed", f"System: Run completed. Response size: {len(report)} chars.")
        
        # Fetch fresh created_at timestamp
        session_info = get_session(session_id)
        created_at_time = session_info.get("created_at") if session_info else ""
        
        return {
            "session_id": session_id,
            "query": query,
            "report": report,
            "created_at": created_at_time
        }
        
    except Exception as e:
        logger.error(f"Research workflow failed for session {session_id}: {e}", exc_info=True)
        send_agent_update(session_id, "System", "failed", f"System: Research workflow failed. Error: {e}")
        update_workflow_run(session_id, "System", "failed", error_message=str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"Research agent workflow failed: {str(e)}"
        )

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: Optional[str] = Query(None)):
    """
    WebSocket channel for clients to receive live multi-agent execution status,
    log streams, and real-time token streaming.
    """
    await ws_manager.connect(websocket, session_id=session_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id=session_id)
    except Exception as e:
        logger.error(f"WebSocket connection error for session {session_id}: {e}")
        ws_manager.disconnect(websocket, session_id=session_id)
