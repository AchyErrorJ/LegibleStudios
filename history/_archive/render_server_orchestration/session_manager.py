import sqlite3
import json
import uuid
from typing import List, Dict, Optional

class SessionManager:
    def __init__(self, db_path="agent_sessions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Creates the tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Table for Sessions (High-level Tasks)
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_query TEXT,
            status TEXT, -- 'active', 'completed', 'failed'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Table for Steps (The Plan)
        c.execute('''CREATE TABLE IF NOT EXISTS plan_steps (
            step_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            tool_name TEXT,
            tool_args TEXT, -- JSON string
            status TEXT,    -- 'pending', 'success', 'error'
            result_summary TEXT,
            step_order INTEGER
        )''')
        
        conn.commit()
        conn.close()

    def create_session(self, user_query: str) -> str:
        """Starts a new task session."""
        session_id = str(uuid.uuid4())[:8] # Short ID
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO sessions (session_id, user_query, status) VALUES (?, ?, ?)",
                  (session_id, user_query, "active"))
        conn.commit()
        conn.close()
        return session_id

    def save_plan(self, session_id: str, steps: List[object]):
        """Saves the Planner's list of TaskStep objects."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Clear old plan if re-planning
        c.execute("DELETE FROM plan_steps WHERE session_id = ? AND status = 'pending'", (session_id,))
        
        for i, step in enumerate(steps):
            # Calculate order index (offset by existing completed steps if any)
            c.execute("INSERT INTO plan_steps (session_id, tool_name, tool_args, status, step_order) VALUES (?, ?, ?, ?, ?)",
                      (session_id, step.tool_name, json.dumps(step.tool_args), "pending", i))
            
        conn.commit()
        conn.close()

    def get_pending_steps(self, session_id: str):
        """Retrieves steps that haven't been done yet."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM plan_steps WHERE session_id = ? AND status = 'pending' ORDER BY step_order ASC", (session_id,))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_history_text(self, session_id: str) -> List[str]:
        """Reconstructs the execution history for the LLM context."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT tool_name, tool_args, result_summary FROM plan_steps WHERE session_id = ? AND status IN ('success', 'error') ORDER BY step_order ASC", (session_id,))
        rows = c.fetchall()
        conn.close()
        
        history = []
        for r in rows:
            history.append(f"- Ran {r[0]}: {r[2]}") # "Ran create_wall: Success ID 123"
        return history

    def mark_step_complete(self, step_db_id: int, status: str, result: str):
        """Updates a step's status after execution."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE plan_steps SET status = ?, result_summary = ? WHERE step_id = ?", 
                  (status, result, step_db_id))
        conn.commit()
        conn.close()