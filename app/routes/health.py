from fastapi import APIRouter
from app.services.llm import check_ollama_status, OLLAMA_BASE_URL
from app.services.database import get_db_connection
from app.services.vector_store import get_or_create_collection
from app.utils.ws_manager import ws_manager
import requests

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    """Verify system health, Ollama status, SQLite availability, and ChromaDB state."""
    # 1. Check Ollama reachable and verify required models are pulled
    ollama_status = "offline"
    ollama_models = []
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            models_data = response.json().get("models", [])
            ollama_models = [m.get("name") for m in models_data]
            ollama_status = "healthy"
    except Exception:
        pass

    # 2. Check Database accessible
    db_status = "offline"
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "healthy"
    except Exception:
        pass

    # 3. Check Vector Store accessible
    vector_status = "offline"
    try:
        collection = get_or_create_collection()
        collection.count()
        vector_status = "healthy"
    except Exception:
        pass

    # 4. Overall status determination
    overall = "healthy"
    if ollama_status == "offline" or db_status == "offline" or vector_status == "offline":
        overall = "offline"
    elif "qwen3:1.7b" not in ollama_models or "qwen3:4b" not in ollama_models:
        overall = "degraded"  # Models are missing but service is up

    return {
        "status": overall,
        "services": {
            "ollama": ollama_status,
            "database": db_status,
            "vector_store": vector_status,
            "websocket": "healthy"
        },
        "models": {
            "available": ollama_models,
            "required_present": "qwen3:1.7b" in ollama_models and "qwen3:4b" in ollama_models
        },
        "active_ws_connections": len(ws_manager.active_connections)
    }
