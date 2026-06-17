import os
import requests
from langchain_ollama import ChatOllama
from app.utils.logging_config import logger

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3:4b")

logger.info(f"LLM: Initializing Single Shared ChatOllama client for model='{MODEL_NAME}'")
# ONE shared singleton instance
llm = ChatOllama(
    model=MODEL_NAME,
    temperature=0.2,
    base_url=OLLAMA_BASE_URL
)

def check_ollama_status() -> bool:
    """Check if the local Ollama service is running and required models are pulled."""
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            models = [m.get("name") for m in response.json().get("models", [])]
            logger.info(f"Ollama connected. Target model: {MODEL_NAME}. Available: {models}")
            # Ensure at least qwen3:4b is pulled
            has_qwen_4b = any("qwen3:4b" in m for m in models)
            has_qwen_1_7b = any("qwen3:1.7b" in m for m in models)
            
            if not has_qwen_4b:
                logger.warning("Required model 'qwen3:4b' is not installed in Ollama. Pull it via: ollama pull qwen3:4b")
            if not has_qwen_1_7b:
                logger.warning("Required model 'qwen3:1.7b' is not installed in Ollama. Pull it via: ollama pull qwen3:1.7b")
                
            return True
        return False
    except Exception as e:
        logger.warning(f"Ollama connection check failed at {OLLAMA_BASE_URL}: {e}")
        return False
