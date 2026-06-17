import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.vector_store import add_document_content
from app.services.database import add_source_to_session, add_uploaded_file
from app.services.tools import read_pdf, analyze_csv, read_docx
from app.utils.text_helpers import ensure_text
from app.models.schemas import UploadResponse
from app.utils.logging_config import logger

router = APIRouter(tags=["Document Ingestion"])

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    session_id: str = Form(..., description="The session ID associated with this document"),
    file: UploadFile = File(...)
):
    """
    Upload a document (PDF, CSV, or TXT) to ingest into the vector database.
    """
    logger.info(f"Upload: Received file '{file.filename}' for session: {session_id}")
    
    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".csv", ".txt", ".docx"]:
        raise HTTPException(status_code=400, detail="Only .pdf, .csv, .txt, and .docx files are supported.")
        
    try:
        # Save uploaded file to a temporary file for parsing
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
            
        # Parse content based on file type
        parsed_content = ""
        summary_snippet = ""
        
        if ext == ".pdf":
            parsed_content = read_pdf(temp_path)
            summary_snippet = parsed_content[:300]
        elif ext == ".csv":
            parsed_content = analyze_csv(temp_path)
            summary_snippet = f"CSV Dataset Summary:\n{parsed_content[:300]}"
        elif ext == ".txt":
            parsed_content = content.decode("utf-8", errors="ignore")
            summary_snippet = parsed_content[:300]
        elif ext == ".docx":
            parsed_content = read_docx(temp_path)
            summary_snippet = parsed_content[:300]
            
        # Clean up temp file
        os.unlink(temp_path)
        
        # Ensure extracted content is safe string data
        parsed_content = ensure_text(parsed_content)
        summary_snippet = ensure_text(summary_snippet)
        
        if not parsed_content.strip():
            raise HTTPException(status_code=400, detail="No readable text could be extracted from the file.")
            
        # Ingest into ChromaDB
        chunks_added = add_document_content(session_id, file.filename, parsed_content)
        
        # Register as a source in SQLite
        add_source_to_session(
            session_id=session_id,
            name=file.filename,
            source_type=ext.replace(".", ""),
            url_or_path=file.filename,
            snippet=summary_snippet
        )
        
        # Register file grounding meta in SQLite
        add_uploaded_file(session_id, file.filename)
        
        return UploadResponse(
            filename=file.filename,
            session_id=session_id,
            chunks=chunks_added,
            message=f"File successfully ingested. Split into {chunks_added} vector chunks."
        )
    except Exception as e:
        logger.error(f"Failed to process uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")
