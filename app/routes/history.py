import os
import uuid
import tempfile
from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.services.database import (
    get_history, get_session, get_session_logs,
    rename_session, delete_session, get_chat_messages,
    get_uploaded_files, get_active_workflow_run,
    create_export_job, update_export_job, get_export_job
)
from app.services.tools import generate_pdf_report, generate_docx_report
from app.models.schemas import HistoryItem, SourceItem, LogItem
from app.utils.logging_config import logger

router = APIRouter(tags=["History, Operations & Exports"])

class RenamePayload(BaseModel):
    title: str

# 1. List history
@router.get("/history", response_model=List[HistoryItem])
def list_history():
    """Retrieve list of all past research sessions."""
    try:
        return get_history()
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history.")

# 2. Get report/session details (updated to recover session state, files, messages)
@router.get("/report/{session_id}")
def get_report(session_id: str):
    """Retrieve full details of a specific session including chat history and status."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    # Recovery and recovery progress checks
    messages = get_chat_messages(session_id)
    uploaded_files = get_uploaded_files(session_id)
    active_run = get_active_workflow_run(session_id)
    
    # Inject values dynamically
    session["chat_history"] = messages
    session["uploaded_files"] = uploaded_files
    session["active_run"] = active_run
    session["status"] = "running" if active_run else "completed"
    
    return session

# 3. Get sources
@router.get("/report/{session_id}/sources")
def get_sources(session_id: str):
    """Retrieve sources referenced in a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session.get("sources", [])

# 4. Get logs
@router.get("/report/{session_id}/logs", response_model=List[LogItem])
def get_logs(session_id: str):
    """Retrieve agent execution logs for a session."""
    return get_session_logs(session_id)

# 5. Rename session thread
@router.put("/session/{session_id}")
def do_rename_session(session_id: str, payload: RenamePayload):
    """Rename a conversation thread title."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    rename_session(session_id, payload.title)
    return {"message": "Session renamed successfully."}

# 6. Delete session thread
@router.delete("/session/{session_id}")
def do_delete_session(session_id: str):
    """Hard delete a conversation session and all its messages."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    delete_session(session_id)
    return {"message": "Session deleted successfully."}


# 7. Asynchronous Export Job System

def run_export_task(job_id: str, session_id: str, export_format: str):
    """Worker task run in background thread pool to generate reports."""
    update_export_job(job_id, "processing")
    
    session = get_session(session_id)
    if not session or not session.get("report"):
        update_export_job(job_id, "failed", error_message="Report content empty or session missing.")
        return
        
    report_text = session["report"]
    query = session["query"]
    
    # Save exports in /storage/exports/
    export_dir = "storage/exports"
    os.makedirs(export_dir, exist_ok=True)
    file_path = f"{export_dir}/{session_id}_{uuid.uuid4().hex[:6]}.{export_format}"
    
    try:
        if export_format == "md":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_text)
        elif export_format == "json":
            import json
            data = {
                "session_id": session_id,
                "query": query,
                "report": report_text,
                "created_at": session.get("created_at"),
                "sources": session.get("sources", []),
                "logs": get_session_logs(session_id)
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        elif export_format == "pdf":
            generate_pdf_report(report_text, file_path, title=f"Research Report: {query}")
        elif export_format == "docx":
            generate_docx_report(report_text, file_path, title=f"Research Report: {query}")
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
            
        update_export_job(job_id, "completed", file_path=file_path)
        logger.info(f"Export Job {job_id} completed successfully. Saved to {file_path}")
    except Exception as e:
        logger.error(f"Export Job {job_id} failed: {e}", exc_info=True)
        update_export_job(job_id, "failed", error_message=str(e))

@router.post("/report/{session_id}/export/{export_format}")
def start_export_job(session_id: str, export_format: str, background_tasks: BackgroundTasks):
    """Queue a background task to export the report."""
    session = get_session(session_id)
    if not session or not session.get("report"):
        raise HTTPException(status_code=404, detail="Report not generated yet.")
        
    export_format = export_format.lower()
    if export_format not in ["md", "pdf", "json", "docx"]:
        raise HTTPException(status_code=400, detail="Invalid format. Supported: md, pdf, json, docx")
        
    job_id = str(uuid.uuid4())
    create_export_job(job_id, session_id, export_format)
    
    # Run export job asynchronously in background thread
    background_tasks.add_task(run_export_task, job_id, session_id, export_format)
    
    return {"job_id": job_id, "status": "queued"}

@router.get("/report/export/status/{job_id}")
def check_export_status(job_id: str):
    """Retrieve status of an asynchronous export job."""
    job = get_export_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found.")
    return job

@router.get("/report/export/download/{job_id}")
def download_export_file(job_id: str):
    """Download the final completed file from the export job."""
    job = get_export_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found.")
    if job["status"] != "completed" or not job["file_path"] or not os.path.exists(job["file_path"]):
        raise HTTPException(status_code=400, detail="Export file is not ready or failed to generate.")
        
    filename = f"Research_Report_{job['session_id'][:8]}.{job['format']}"
    
    # Match media types
    media_types = {
        "md": "text/markdown",
        "pdf": "application/pdf",
        "json": "application/json",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    
    return FileResponse(
        path=job["file_path"],
        filename=filename,
        media_type=media_types.get(job["format"], "application/octet-stream")
    )
