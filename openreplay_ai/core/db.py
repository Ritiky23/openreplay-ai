import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

class DBManager:
    _db_path: str = os.path.join(".openreplay", "traces.db")

    @classmethod
    def set_db_path(cls, path: str):
        cls._db_path = path

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        # Ensure directory exists
        db_dir = os.path.dirname(cls._db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        conn = sqlite3.connect(cls._db_path, timeout=30.0)
        # Enable WAL mode for concurrent execution and better performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        with cls.get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                total_latency REAL,
                total_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                metadata TEXT, -- JSON
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_steps (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                parent_step_id TEXT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                latency REAL,
                status TEXT NOT NULL,
                inputs TEXT, -- JSON
                outputs TEXT, -- JSON
                token_count INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                model_used TEXT,
                error_details TEXT, -- JSON
                metadata TEXT, -- JSON
                FOREIGN KEY(trace_id) REFERENCES traces(id)
            );
            """)
            conn.commit()

    @classmethod
    def create_trace(cls, trace_id: str, name: str, status: str = "running", metadata: Optional[Dict] = None) -> bool:
        cls.init_db()
        created_at = datetime.utcnow().isoformat()
        metadata_str = json.dumps(metadata) if metadata else None
        try:
            with cls.get_connection() as conn:
                conn.execute(
                    "INSERT INTO traces (id, name, status, created_at, metadata) VALUES (?, ?, ?, ?, ?)",
                    (trace_id, name, status, created_at, metadata_str)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    @classmethod
    def update_trace(cls, trace_id: str, status: str, total_latency: float, total_tokens: int, total_cost: float, metadata: Optional[Dict] = None):
        cls.init_db()
        metadata_str = json.dumps(metadata) if metadata else None
        with cls.get_connection() as conn:
            if metadata_str:
                conn.execute(
                    "UPDATE traces SET status = ?, total_latency = ?, total_tokens = ?, total_cost = ?, metadata = ? WHERE id = ?",
                    (status, total_latency, total_tokens, total_cost, metadata_str, trace_id)
                )
            else:
                conn.execute(
                    "UPDATE traces SET status = ?, total_latency = ?, total_tokens = ?, total_cost = ? WHERE id = ?",
                    (status, total_latency, total_tokens, total_cost, trace_id)
                )
            conn.commit()

    @classmethod
    def upsert_step(cls, step_id: str, trace_id: str, parent_step_id: Optional[str], name: str, type: str,
                    start_time: float, end_time: Optional[float] = None, latency: Optional[float] = None,
                    status: str = "running", inputs: Optional[Any] = None, outputs: Optional[Any] = None,
                    token_count: Optional[int] = None, cost: Optional[float] = None, model_used: Optional[str] = None,
                    error_details: Optional[Dict] = None, metadata: Optional[Dict] = None):
        cls.init_db()
        
        start_time_iso = datetime.utcfromtimestamp(start_time).isoformat()
        end_time_iso = datetime.utcfromtimestamp(end_time).isoformat() if end_time else None
        
        inputs_str = json.dumps(inputs) if inputs is not None else None
        outputs_str = json.dumps(outputs) if outputs is not None else None
        error_str = json.dumps(error_details) if error_details is not None else None
        metadata_str = json.dumps(metadata) if metadata is not None else None

        with cls.get_connection() as conn:
            # Check if exists
            cursor = conn.execute("SELECT 1 FROM trace_steps WHERE id = ?", (step_id,))
            exists = cursor.fetchone()
            
            if exists:
                conn.execute("""
                    UPDATE trace_steps SET 
                        end_time = ?, latency = ?, status = ?, 
                        inputs = COALESCE(?, inputs), 
                        outputs = COALESCE(?, outputs), 
                        token_count = COALESCE(?, token_count), 
                        cost = COALESCE(?, cost), 
                        model_used = COALESCE(?, model_used), 
                        error_details = COALESCE(?, error_details), 
                        metadata = COALESCE(?, metadata)
                    WHERE id = ?
                """, (
                    end_time_iso, latency, status, 
                    inputs_str, outputs_str, 
                    token_count, cost, 
                    model_used, error_str, metadata_str, 
                    step_id
                ))
            else:
                conn.execute("""
                    INSERT INTO trace_steps (
                        id, trace_id, parent_step_id, name, type, start_time, end_time, latency, status,
                        inputs, outputs, token_count, cost, model_used, error_details, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    step_id, trace_id, parent_step_id, name, type, start_time_iso, end_time_iso, latency, status,
                    inputs_str, outputs_str, 
                    token_count if token_count is not None else 0, 
                    cost if cost is not None else 0.0, 
                    model_used, error_str, metadata_str
                ))
            conn.commit()

    @classmethod
    def get_all_traces(cls) -> List[Dict[str, Any]]:
        cls.init_db()
        with cls.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM traces ORDER BY created_at DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                trace_dict = dict(row)
                trace_dict["metadata"] = json.loads(trace_dict["metadata"]) if trace_dict.get("metadata") else {}
                result.append(trace_dict)
            return result

    @classmethod
    def get_trace_tree(cls, trace_id: str) -> Dict[str, Any]:
        cls.init_db()
        with cls.get_connection() as conn:
            # Get trace
            cursor = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,))
            trace_row = cursor.fetchone()
            if not trace_row:
                return {}
            
            trace_dict = dict(trace_row)
            trace_dict["metadata"] = json.loads(trace_dict["metadata"]) if trace_dict.get("metadata") else {}
            
            # Get steps
            cursor = conn.execute("SELECT * FROM trace_steps WHERE trace_id = ? ORDER BY start_time ASC", (trace_id,))
            step_rows = cursor.fetchall()
            steps = []
            for row in step_rows:
                step_dict = dict(row)
                step_dict["inputs"] = json.loads(step_dict["inputs"]) if step_dict.get("inputs") else None
                step_dict["outputs"] = json.loads(step_dict["outputs"]) if step_dict.get("outputs") else None
                step_dict["error_details"] = json.loads(step_dict["error_details"]) if step_dict.get("error_details") else None
                step_dict["metadata"] = json.loads(step_dict["metadata"]) if step_dict.get("metadata") else {}
                steps.append(step_dict)
                
            trace_dict["steps"] = steps
            return trace_dict
