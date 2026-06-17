import os
import sqlite3
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.utils.logging_config import logger

# Relocate database to db/ directory to prevent watchfile triggers on root writes
DB_PATH = os.getenv("DATABASE_PATH", "db/research_platform.db")
db_lock = threading.Lock()

# Define explicitly the columns that map directly to the SQLite schema
VALID_SESSION_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "query": "TEXT NOT NULL",
    "intent": "TEXT",
    "goal": "TEXT",
    "plan": "TEXT",
    "sources": "TEXT",          # JSON string (list of source dicts)
    "research_notes": "TEXT",
    "report": "TEXT",
    "confidence_score": "REAL",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT"
}

def serialize(value: Any) -> Any:
    """Serialize list, dict, set, or other JSON-compatible objects to JSON string."""
    if isinstance(value, (list, dict, set)):
        if isinstance(value, set):
            value = list(value)
        return json.dumps(value)
    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        try:
            return json.dumps(value.dict())
        except Exception:
            pass
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return json.dumps(value.model_dump())
        except Exception:
            pass
    return value

def deserialize(value: Any) -> Any:
    """Deserialize JSON string to Python list or dict if applicable."""
    if isinstance(value, str):
        trimmed = value.strip()
        if (trimmed.startswith("[") and trimmed.endswith("]")) or (trimmed.startswith("{") and trimmed.endswith("}")):
            try:
                return json.loads(value)
            except Exception:
                pass
    return value

def get_db_connection():
    """Create a new SQLite connection with dict factory and busy timeout of 30.0s."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def ensure_session_exists(cursor, session_id: str, now: str) -> None:
    """Ensures a session exists in the research_sessions table to avoid foreign key violations."""
    cursor.execute("SELECT 1 FROM research_sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO research_sessions (id, query, created_at) VALUES (?, ?, ?)",
            (session_id, f"Auto-Created Session {session_id}", now)
        )

def init_db():
    """Initialize database tables if they do not exist and automatically migrate schema."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Create main research_sessions table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_sessions (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                goal TEXT,
                plan TEXT,
                sources TEXT,
                research_notes TEXT,
                report TEXT,
                confidence_score REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        
        # 2. Create execution_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                log_message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)

        # 3. Create workflow_runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                current_agent TEXT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)

        # 4. Create chat_messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)

        # 5. Create reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)

        # 6. Create uploaded_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)

        # 7. Create cache_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)

        # 8. Create export_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_jobs (
                job_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                format TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (session_id) REFERENCES research_sessions (id) ON DELETE CASCADE
            )
        """)
        
        # 9. Run migrations: dynamically inspect research_sessions columns and add missing ones
        cursor.execute("PRAGMA table_info(research_sessions)")
        existing_cols = {row['name'] for row in cursor.fetchall()}
        
        for col_name, col_type in VALID_SESSION_COLUMNS.items():
            if col_name not in existing_cols:
                logger.info(f"Database migration: Adding missing column '{col_name}' to research_sessions")
                cursor.execute(f"ALTER TABLE research_sessions ADD COLUMN {col_name} {col_type.replace('PRIMARY KEY', '').replace('NOT NULL', '')}")
        
        conn.commit()
        conn.close()
    logger.info(f"SQLite Database initialized and verified at {DB_PATH}")

def create_session(session_id: str, query: str) -> None:
    """Create a new research session in the database."""
    now = datetime.now().isoformat()
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO research_sessions (id, query, created_at) VALUES (?, ?, ?)",
            (session_id, query, now)
        )
        conn.commit()
        conn.close()
    logger.info(f"Database: Created session {session_id} for query '{query}'")

def update_session(session_id: str, **kwargs) -> None:
    """
    Update dynamic fields of a research session.
    Strictly filters out keys not in the schema and automatically 
    serializes dictionaries/lists/sets into JSON strings.
    """
    if not kwargs:
        return
        
    filtered_kwargs = {}
    for k, v in kwargs.items():
        db_key = k
        if k == "final_report":
            db_key = "report"
            
        if db_key in VALID_SESSION_COLUMNS:
            filtered_kwargs[db_key] = serialize(v)
            
    if not filtered_kwargs:
        return
        
    # Automatically add updated_at timestamp
    filtered_kwargs["updated_at"] = datetime.now().isoformat()
    
    set_clause = ", ".join([f"{k} = ?" for k in filtered_kwargs.keys()])
    params = list(filtered_kwargs.values()) + [session_id]
    
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = f"UPDATE research_sessions SET {set_clause} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            conn.close()
        logger.info(f"Database: Updated session {session_id} successfully.")
    except Exception as e:
        logger.error(f"Database: Failed to update session {session_id}: {e}", exc_info=True)

def add_source_to_session(session_id: str, name: str, source_type: str, url_or_path: Optional[str] = None, snippet: Optional[str] = None) -> None:
    """
    Appends a new source dictionary to the session's 'sources' JSON array column.
    """
    session = get_session(session_id)
    if not session:
        return
        
    sources_list = session.get("sources") or []
    if not isinstance(sources_list, list):
        sources_list = []
            
    sources_list.append({
        "name": name,
        "type": source_type,
        "url_or_path": url_or_path,
        "snippet": snippet
    })
    
    update_session(session_id, sources=sources_list)

def add_execution_log(session_id: str, agent_name: str, log_message: str) -> None:
    """Log an execution step for a research session, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                """
                INSERT INTO execution_logs (session_id, agent_name, log_message, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, agent_name, log_message, now)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Failed to write execution log to DB: {e}")
        
    logger.info(f"[{agent_name}] {log_message}")

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve details of a single research session, deserializing json values."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM research_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        session_data = dict(row)
        for k, v in session_data.items():
            session_data[k] = deserialize(v)
            
        return session_data
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        return None

def get_history() -> List[Dict[str, Any]]:
    """Get all past research sessions sorted by creation time, with message count."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.id, s.query, s.created_at, s.report IS NOT NULL as completed,
            (SELECT COUNT(*) FROM chat_messages WHERE session_id = s.id) as message_count
            FROM research_sessions s 
            ORDER BY s.created_at DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return []

def get_session_logs(session_id: str) -> List[Dict[str, Any]]:
    """Get all execution logs associated with a session."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM execution_logs WHERE session_id = ? ORDER BY id ASC", (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving logs for session {session_id}: {e}")
        return []

# New chat message helper functions
def add_chat_message(session_id: str, role: str, content: str) -> None:
    """Add a prompt or assistant message in SQLite, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now)
            )
            conn.commit()
            conn.close()
        logger.info(f"Database: Saved message for session {session_id} (Role: {role})")
    except Exception as e:
        logger.error(f"Database: Failed to save message: {e}")

def get_chat_messages(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve chat history sequence for a session."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Database: Failed to get messages: {e}")
        return []

# New reports tables helper functions
def add_report(session_id: str, report_id: str, content: str) -> None:
    """Save generated report state, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                "INSERT OR REPLACE INTO reports (report_id, session_id, content, timestamp) VALUES (?, ?, ?, ?)",
                (report_id, session_id, content, now)
            )
            conn.commit()
            conn.close()
        logger.info(f"Database: Saved report {report_id} under session {session_id}")
    except Exception as e:
        logger.error(f"Database: Failed to save report: {e}")

def get_reports(session_id: str) -> List[Dict[str, Any]]:
    """Get all reports generated inside a session."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT report_id, content, timestamp FROM reports WHERE session_id = ? ORDER BY timestamp DESC",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Database: Failed to get reports: {e}")
        return []

# New uploaded files helper functions
def add_uploaded_file(session_id: str, filename: str) -> None:
    """Save metadata of grounding document, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                "INSERT INTO uploaded_files (session_id, filename, uploaded_at) VALUES (?, ?, ?)",
                (session_id, filename, now)
            )
            conn.commit()
            conn.close()
        logger.info(f"Database: Registered uploaded file '{filename}' under session {session_id}")
    except Exception as e:
        logger.error(f"Database: Failed to save uploaded file: {e}")

def get_uploaded_files(session_id: str) -> List[str]:
    """Retrieve grounding documents metadata."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM uploaded_files WHERE session_id = ? ORDER BY id ASC", (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [row["filename"] for row in rows]
    except Exception as e:
        logger.error(f"Database: Failed to get uploaded files: {e}")
        return []

# Session delete and rename helpers
def delete_session(session_id: str) -> None:
    """Hard-delete session and cascade related details."""
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
            conn.commit()
            conn.close()
        logger.info(f"Database: Successfully deleted session {session_id} and all cascaded entries")
    except Exception as e:
        logger.error(f"Database: Failed to delete session {session_id}: {e}")

def rename_session(session_id: str, title: str) -> None:
    """Rename session thread."""
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE research_sessions SET query = ? WHERE id = ?", (title, session_id))
            conn.commit()
            conn.close()
        logger.info(f"Database: Renamed session {session_id} query to '{title}'")
    except Exception as e:
        logger.error(f"Database: Failed to rename session {session_id}: {e}")

# SQLite caching layer helpers
def get_cached_val(key: str) -> Optional[Any]:
    """Get active value from cache."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM cache_entries WHERE key = ? AND expires_at > ?", (key, now))
            row = cursor.fetchone()
            conn.close()
            if row:
                return deserialize(row["value"])
    except Exception as e:
        logger.error(f"Database: Cache fetch failed for '{key}': {e}")
    return None

def set_cached_val(key: str, value: Any, ttl_seconds: int = 3600) -> None:
    """Set cache value with TTL expiration."""
    now = datetime.now()
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    val_str = serialize(value)
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO cache_entries (key, value, expires_at) VALUES (?, ?, ?)",
                (key, val_str, expires_at)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Database: Cache store failed for '{key}': {e}")

# Workflow Runs persistence and recovery
def create_workflow_run(run_id: str, session_id: str, current_agent: str, status: str) -> None:
    """Create a new step tracker run, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                """
                INSERT INTO workflow_runs (run_id, session_id, current_agent, status, started_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, session_id, current_agent, status, now, now)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Database: Failed to create workflow run: {e}")

def update_workflow_run(session_id: str, current_agent: str, status: str, error_message: Optional[str] = None) -> None:
    """Update workflow step state, guaranteeing session exists."""
    now = datetime.now().isoformat()
    completed_at = now if status in ["completed", "failed"] else None
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                """
                UPDATE workflow_runs 
                SET current_agent = ?, status = ?, updated_at = ?, completed_at = ?, error_message = ?
                WHERE session_id = ? AND completed_at IS NULL
                """,
                (current_agent, status, now, completed_at, error_message, session_id)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Database: Failed to update workflow run: {e}")

def get_active_workflow_run(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve active running workflow for recovery."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM workflow_runs 
            WHERE session_id = ? AND status = 'running' 
            ORDER BY started_at DESC LIMIT 1
            """,
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Database: Failed to get active workflow run: {e}")
        return None

# Export Jobs database helpers
def create_export_job(job_id: str, session_id: str, format_type: str) -> None:
    """Initialize an export job, guaranteeing session exists."""
    now = datetime.now().isoformat()
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            ensure_session_exists(cursor, session_id, now)
            cursor.execute(
                """
                INSERT INTO export_jobs (job_id, session_id, format, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, session_id, format_type, "queued", now)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Database: Failed to create export job: {e}")

def update_export_job(job_id: str, status: str, file_path: Optional[str] = None, error_message: Optional[str] = None) -> None:
    """Update progress of an export job."""
    now = datetime.now().isoformat()
    completed_at = now if status in ["completed", "failed"] else None
    try:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE export_jobs 
                SET status = ?, file_path = ?, error_message = ?, completed_at = ?
                WHERE job_id = ?
                """,
                (status, file_path, error_message, completed_at, job_id)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Database: Failed to update export job: {e}")

def get_export_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Check status of an export job."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM export_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Database: Failed to get export job: {e}")
        return None
