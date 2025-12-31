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
            # 5. Presets Table (Actor/Stage templates)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT, -- 'actor' or 'stage'
                    name TEXT,
                    content_json TEXT, -- All configuration data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 6. LLM Providers Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    api_key TEXT,
                    base_url TEXT,
                    model TEXT,
                    status TEXT,
                    fetched_models_json TEXT, -- List of available models
                    is_favorite INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def get_all_scripts(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, topic, created_at FROM scripts ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_script_by_id(self, script_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["content"] = json.loads(d.pop("content_json", "[]"))
                return d
            return None

    def delete_script(self, script_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scripts WHERE id = ?", (script_id,))

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

    # --- Provider Methods ---
    def save_provider(self, config: Dict):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO llm_providers 
                (name, api_key, base_url, model, status, fetched_models_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                config["name"], 
                config["api_key"], 
                config["base_url"], 
                config.get("model", "default"),
                config.get("status", "unknown"),
                json.dumps(config.get("fetched_models", []))
            ))

    def load_providers(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM llm_providers")
            rows = cursor.fetchall()
            configs = []
            for row in rows:
                d = dict(row)
                d["fetched_models"] = json.loads(d.pop("fetched_models_json", "[]"))
                configs.append(d)
            return configs

    def delete_provider(self, name: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM llm_providers WHERE name = ?", (name,))

    # --- Preset Methods (Project Snapshots) ---
    def save_unique_preset(self, p_type: str, name: str, content: Dict):
        """Saves a preset, overwriting if same name and type exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Check existing
            cursor.execute("SELECT id FROM presets WHERE type=? AND name=?", (p_type, name))
            row = cursor.fetchone()
            
            if row:
                cursor.execute(
                    "UPDATE presets SET content_json=?, created_at=CURRENT_TIMESTAMP WHERE id=?", 
                    (json.dumps(content), row[0])
                )
            else:
                cursor.execute(
                    "INSERT INTO presets (type, name, content_json) VALUES (?, ?, ?)",
                    (p_type, name, json.dumps(content))
                )

    def get_presets(self, p_type: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, created_at FROM presets WHERE type=? ORDER BY created_at DESC", (p_type,))
            return [dict(row) for row in cursor.fetchall()]

    def get_preset_by_id(self, pid: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM presets WHERE id=?", (pid,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["content"] = json.loads(d.pop("content_json", "{}"))
                return d
            return None

    def delete_preset(self, pid: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM presets WHERE id=?", (pid,))
