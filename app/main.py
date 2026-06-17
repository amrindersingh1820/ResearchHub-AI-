import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable watchfiles logging to help debug file changes causing restarts
logging.getLogger("watchfiles").setLevel(logging.INFO)

from app.utils.logging_config import logger
from app.services.database import init_db
from app.services.llm import check_ollama_status
from app.routes import health, upload, research, history

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent AI Research Platform",
    description="Production-grade AI Research Platform using LangGraph, Ollama (Qwen3), and FastAPI.",
    version="1.0.0"
)

# Set up CORS middleware to allow connections from local React apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def on_startup():
    import asyncio
    from app.utils.ws_manager import ws_manager
    ws_manager.main_loop = asyncio.get_running_loop()
    
    logger.info("Initializing SQLite database...")
    init_db()
    
    logger.info("Verifying Ollama service status...")
    check_ollama_status()
    
# Register routers
app.include_router(health.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(history.router, prefix="/api")

# Handle root redirect or simple message
@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Multi-Agent AI Research Platform API",
        "docs_url": "/docs",
        "health_check": "/api/health"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "app.main:app", 
        host=host, 
        port=port, 
        reload=True,
        reload_excludes=[
            "*.db",
            "*.db-journal",
            "*.db-wal",
            "*.db-shm",
            "storage/*",
            "db/*",
            "logs/*"
        ]
    )
