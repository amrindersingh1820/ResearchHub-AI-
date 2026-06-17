import asyncio
from fastapi import WebSocket
from typing import List, Dict, Set, Any, Optional
from app.utils.logging_config import logger
from app.services.database import add_execution_log

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connections_by_session: Dict[str, Set[WebSocket]] = {}
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        """Accept WebSocket connection and register it to a session."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.main_loop = asyncio.get_running_loop()
        
        if session_id:
            # Reconnection/Ownership architecture: close previous active sockets of this session
            if session_id not in self.connections_by_session:
                self.connections_by_session[session_id] = set()
            
            old_sockets = list(self.connections_by_session[session_id])
            for old_ws in old_sockets:
                logger.info(f"WebSocket: Replaced duplicate socket connection for session {session_id}")
                try:
                    await old_ws.close(code=1001, reason="Reconnected on another tab/instance")
                except Exception:
                    pass
                self.active_connections.discard(old_ws)
                self.connections_by_session[session_id].discard(old_ws)
            
            self.connections_by_session[session_id].add(websocket)
            logger.info(f"WebSocket: Client registered under session {session_id}. Active: {len(self.active_connections)}")
        else:
            logger.info(f"WebSocket: Anonymous client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, session_id: Optional[str] = None):
        """Clean up websocket connection registration."""
        self.active_connections.discard(websocket)
        if session_id and session_id in self.connections_by_session:
            self.connections_by_session[session_id].discard(websocket)
            if not self.connections_by_session[session_id]:
                del self.connections_by_session[session_id]
        logger.info(f"WebSocket: Client disconnected. Active connections remaining: {len(self.active_connections)}")

    async def broadcast_json(self, data: Dict[str, Any]):
        """Broadcast JSON update to all active websocket connections mapped to target session or global."""
        session_id = data.get("session_id")
        targets = set()
        
        if session_id and session_id in self.connections_by_session:
            targets = self.connections_by_session[session_id]
        else:
            targets = self.active_connections
            
        dead_connections = []
        for connection in list(targets):
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"WebSocket broadcast failed for a socket: {e}")
                dead_connections.append(connection)
                
        # Clean stale connections automatically
        for conn in dead_connections:
            self.active_connections.discard(conn)
            if session_id and session_id in self.connections_by_session:
                self.connections_by_session[session_id].discard(conn)

ws_manager = ConnectionManager()

def send_agent_update(session_id: str, agent_name: str, status: str, log_message: str, elapsed: Optional[float] = None) -> None:
    """
    Saves execution log to the DB and broadcasts real-time updates to connected WebSockets.
    Works safely from both synchronous and asynchronous contexts.
    """
    # 1. Persist log to SQLite
    try:
        add_execution_log(session_id, agent_name, log_message)
    except Exception as e:
        logger.error(f"Failed to record database log for {agent_name}: {e}")

    # 2. Package WS Payload
    payload = {
        "session_id": session_id,
        "agent": agent_name,
        "status": status,
        "log": log_message,
        "elapsed": elapsed
    }
    
    coro = ws_manager.broadcast_json(payload)
    
    # 3. Schedule broadcast on the main running event loop in a thread-safe way
    if ws_manager.main_loop and ws_manager.main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(coro, ws_manager.main_loop)
        except Exception as e:
            logger.error(f"Failed to schedule WebSocket broadcast: {e}")
            coro.close()
    else:
        coro.close()

def send_agent_chunk(session_id: str, agent_name: str, chunk: str) -> None:
    """
    Sends streaming tokens in real time over WebSockets to reduce UI rendering lag.
    """
    payload = {
        "session_id": session_id,
        "agent": agent_name,
        "status": "streaming",
        "chunk": chunk
    }
    coro = ws_manager.broadcast_json(payload)
    
    if ws_manager.main_loop and ws_manager.main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(coro, ws_manager.main_loop)
        except Exception as e:
            coro.close()
    else:
        coro.close()
