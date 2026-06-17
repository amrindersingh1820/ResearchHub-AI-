import json
from typing import Any

def ensure_text(data: Any) -> str:
    """
    Safely convert incoming state data to string format.
    Handles None, lists of strings, dicts, tuples, and LangChain Document objects.
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "\n".join(
            ensure_text(item)
            for item in data
        )
    if isinstance(data, dict):
        try:
            return json.dumps(data, indent=2)
        except Exception:
            return str(data)
    if hasattr(data, "page_content"):
        return str(data.page_content)
    return str(data)
