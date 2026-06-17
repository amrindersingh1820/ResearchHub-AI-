import operator
from typing import TypedDict, List, Dict, Any, Annotated

class AgentState(TypedDict):
    """
    State model representing the multi-agent routing and execution workflow.
    """
    query: str
    intent: str  # 'research', 'code', 'general', or 'follow_up'
    goal: str
    plan: str
    sources: Annotated[List[Dict[str, Any]], operator.add]
    retrieved_chunks: Annotated[List[str], operator.add]
    research_notes: str
    final_report: str
    session_id: str
    status: str
    execution_log: Annotated[List[str], operator.add]
    chat_history: List[Dict[str, str]]  # list of {"role": role, "content": content}
