from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ResearchRequest(BaseModel):
    query: str = Field(..., description="The main topic or question to research", min_length=3)
    session_id: Optional[str] = Field(None, description="Optional pre-generated session ID to link uploads")

class ResearchResponse(BaseModel):
    session_id: str
    query: str
    report: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: str

class HistoryItem(BaseModel):
    id: str
    query: str
    created_at: str
    completed: bool

class UploadResponse(BaseModel):
    filename: str
    session_id: str
    chunks: int
    message: str

class SourceItem(BaseModel):
    id: int
    session_id: str
    name: str
    type: str
    url_or_path: Optional[str] = None
    snippet: Optional[str] = None

class LogItem(BaseModel):
    id: int
    session_id: str
    agent_name: str
    log_message: str
    timestamp: str
