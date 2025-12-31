import sqlite3
import json
from typing import List, Dict, Any, Optional

class PersonaLibrary:
    """
    Manages a persistent library of 'Signed Actors' (LLM personas).
    Allows users to save and reuse character settings.
    """
    
    def __init__(self, db_path: str = "theater.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actors_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    avatar TEXT,
                    system_prompt TEXT,
                    private_memory TEXT,
                    tags TEXT, -- JSON string of tags
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save_persona(self, name: str, system_prompt: str, avatar: str = "", private_memory: str = "", tags: List[str] = None):
        """Saves or updates a persona in the library."""
        tags_json = json.dumps(tags or [])
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO actors_library (name, avatar, system_prompt, private_memory, tags)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    avatar=excluded.avatar,
                    system_prompt=excluded.system_prompt,
                    private_memory=excluded.private_memory,
                    tags=excluded.tags
            """, (name, avatar, system_prompt, private_memory, tags_json))

    def get_persona(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific persona by name."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM actors_library WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "avatar": row[2],
                    "system_prompt": row[3],
                    "private_memory": row[4],
                    "tags": json.loads(row[5])
                }
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """Lists all personas in the library."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM actors_library")
            return [{
                "id": row[0],
                "name": row[1],
                "avatar": row[2],
                "system_prompt": row[3],
                "private_memory": row[4],
                "tags": json.loads(row[5])
            } for row in cursor.fetchall()]

    def delete_persona(self, name: str):
        """Deletes a persona from the library."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM actors_library WHERE name = ?", (name,))
