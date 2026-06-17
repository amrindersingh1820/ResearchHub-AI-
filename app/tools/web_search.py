import os
import requests
from typing import List, Dict, Any
from abc import ABC, abstractmethod
from app.utils.logging_config import logger

class BaseWebSearch(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        pass

class TavilySearch(BaseWebSearch):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.tavily.com/search"

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            logger.info(f"TavilySearch: Executing query '{query}'")
            response = requests.post(
                self.url,
                json={"api_key": self.api_key, "query": query, "max_results": limit},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", "No Title"),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0)
                })
            return results
        except Exception as e:
            logger.error(f"TavilySearch failed, falling back: {e}")
            return []

class DDGSearch(BaseWebSearch):
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Real-time free DuckDuckGo search using duckduckgo-search library."""
        try:
            logger.info(f"DDGSearch: Executing query '{query}'")
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=limit))
                formatted = []
                for item in results:
                    formatted.append({
                        "title": item.get("title", "No Title"),
                        "url": item.get("href", ""),
                        "content": item.get("body", "")
                    })
                return formatted
        except Exception as e:
            logger.error(f"DDGSearch failed, falling back to mock: {e}")
            return []

class MockSearch(BaseWebSearch):
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"MockSearch: Simulating research query '{query}'")
        
        lower_query = query.lower()
        results = []
        
        if "cybersecurity" in lower_query or "security" in lower_query:
            results = [
                {
                    "title": "AI in Threat Detection: 2026 Landscape",
                    "url": "https://cybersecurity-institute.org/ai-detection-2026",
                    "content": "Machine learning models have transitioned to real-time graph embeddings, allowing sub-millisecond detection of polymorphic malware and credential stuffing attacks."
                },
                {
                    "title": "Autonomous Penetration Testing Frameworks",
                    "url": "https://infosecjournal.net/autonomous-pentest-agents",
                    "content": "Multi-agent systems using LangGraph are being deployed to dynamically inspect cloud service postures, execute safe exploits, and draft remediation plans."
                }
            ]
        elif "health" in lower_query or "medical" in lower_query:
            results = [
                {
                    "title": "Clinical Agentic Workflows for Diagnosis support",
                    "url": "https://healthai-consortium.org/agentic-clinical-support",
                    "content": "LangGraph-driven diagnostic agents assist radiologists by cross-referencing MRI scans against patient history and academic journals."
                }
            ]
        else:
            results = [
                {
                    "title": f"Recent Advances in {query}",
                    "url": "https://techresearch-portal.net/advancements",
                    "content": f"New research on {query} highlights significant integration with Agentic AI, decentralized vector data retrieval, and local small-parameter models."
                }
            ]
            
        return results[:limit]

def get_web_search_provider() -> BaseWebSearch:
    """Instantiate the correct search provider based on environment config, falling back to DDG, then Mock."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        return TavilySearch(tavily_key)
    
    # Try real DuckDuckGo search first
    return DDGSearch()
