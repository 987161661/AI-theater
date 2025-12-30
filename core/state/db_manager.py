import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

class DBManager:
    """
    Handles SQLite persistence for AI Theater.
    Stores scripts, actor states, and performance logs.
    """
    def __init__(self, db_path: str = "theater.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Scripts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT,
                    content_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. Performances Table (Sessions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id INTEGER,
                    status TEXT, -- 'running', 'paused', 'finished'
                    current_index INTEGER DEFAULT 0,
                    world_bible_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (script_id) REFERENCES scripts (id)
                )
            """)
            
            # 3. Actors Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actor_states (
                    performance_id INTEGER,
                    actor_name TEXT,
                    persona_json TEXT, -- system_prompt, nickname, etc.
                    memory_json TEXT,  -- initial_memories
                    current_memory TEXT,
                    PRIMARY KEY (performance_id, actor_name),
                    FOREIGN KEY (performance_id) REFERENCES performances (id)
                )
            """)
            
            # 4. Logs (Dialogue History)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    performance_id INTEGER,
                    actor_name TEXT,
                    msg_type TEXT, -- 'dialogue', 'stage_direction', 'system'
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (performance_id) REFERENCES performances (id)
                )
            """)
            conn.commit()

    def save_script(self, topic: str, content: Dict) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scripts (topic, content_json) VALUES (?, ?)",
                (topic, json.dumps(content))
            )
            return cursor.lastrowid

    def create_performance(self, script_id: int, world_bible: Dict) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO performances (script_id, status, world_bible_json) VALUES (?, 'initialized', ?)",
                (script_id, json.dumps(world_bible))
            )
            return cursor.lastrowid

    def update_performance_status(self, perf_id: int, status: str, current_index: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE performances SET status = ?, current_index = ? WHERE id = ?",
                (status, current_index, perf_id)
            )

    def save_actor_state(self, perf_id: int, name: str, persona: Dict, memories: List[str]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO actor_states 
                (performance_id, actor_name, persona_json, memory_json, current_memory)
                VALUES (?, ?, ?, ?, ?)
            """, (perf_id, name, json.dumps(persona), json.dumps(memories), "\n".join(memories)))

    def log_event(self, perf_id: int, actor: str, msg_type: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO performance_logs (performance_id, actor_name, msg_type, content) VALUES (?, ?, ?, ?)",
                (perf_id, actor, msg_type, content)
            )

    def get_latest_performance(self) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM performances ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None
