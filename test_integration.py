import os
import asyncio
import uuid
from dotenv import load_dotenv

# Load configurations
load_dotenv()

from app.services.database import init_db, get_session, get_session_logs
from app.services.llm import check_ollama_status
from app.graph.workflow import research_graph
from app.utils.logging_config import logger

async def run_single_test(query: str, expected_intent: str):
    from app.utils.ws_manager import ws_manager
    ws_manager.main_loop = asyncio.get_running_loop()

    session_id = f"test-{expected_intent}-{uuid.uuid4().hex[:8]}"
    print(f"\n--- Testing Query: '{query}' (Expected Intent: {expected_intent}) ---")
    
    initial_state = {
        "query": query,
        "intent": "",
        "goal": "",
        "plan": "",
        "sources": [],
        "retrieved_chunks": [],
        "research_notes": "",
        "final_report": "",
        "session_id": session_id,
        "status": "Started",
        "execution_log": [f"System: Starting CLI integration test for '{query}'."]
    }
    
    config = {"configurable": {"session_id": session_id}}
    
    try:
        final_state = await research_graph.ainvoke(initial_state, config=config)
        
        print("Results:")
        print(f"  Detected Intent: {final_state.get('intent')}")
        print(f"  Status: {final_state.get('status')}")
        print(f"  Final Report Length: {len(final_state.get('final_report', ''))} characters")
        if expected_intent == "code":
            print("  Code Snippet Output:")
            print("-" * 40)
            print(final_state.get("final_report"))
            print("-" * 40)
        else:
            snippet = final_state.get("final_report", "")[:150].replace("\n", " ")
            print(f"  Report Snippet: {snippet}...")
            
        logs = get_session_logs(session_id)
        print(f"  SQLite logs recorded: {len(logs)}")
        
        # Verify the intent matches
        assert final_state.get("intent") == expected_intent, f"Expected intent {expected_intent}, but got {final_state.get('intent')}"
        print(f"SUCCESS: Query '{query}' correctly routed to {expected_intent}!")
    except Exception as e:
        print(f"FAIL: Query '{query}' failed with error: {e}")
        logger.error(f"Test failed for '{query}'", exc_info=True)
        raise e

async def run_all_tests():
    print("=" * 60)
    print("Multi-Agent Router & Research System: Integration Flow Test")
    print("=" * 60)
    
    # 1. Initialize SQLite Database
    print("\n[1/3] Initializing SQLite database...")
    init_db()
    
    # 2. Check Ollama Daemon
    print("\n[2/3] Checking Ollama service availability...")
    ollama_running = check_ollama_status()
    if not ollama_running:
        print("WARNING: Ollama service is not running or model is missing.")
        print("Please run: 'ollama serve' and pull the model.")
        print("Proceeding with tests...")
        
    # 3. Run queries for Research, Code, and General intents
    print("\n[3/3] Running intent validation tests...")
    await run_single_test("Research AI applications in space exploration", "research")
    await run_single_test("Write a basic C program", "code")
    await run_single_test("Hello, who are you?", "general")
    
    print("\n" + "=" * 60)
    print("SUCCESS: All integration tests completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
