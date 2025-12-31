import json
import sqlite3
from typing import List, Dict, Any, Optional

class PresetManager:
    """
    Handles saving and loading of Actor and Stage presets.
    """
    def __init__(self, db_path: str = "theater.db"):
        self.db_path = db_path

    def save_preset(self, preset_type: str, name: str, content: Dict[str, Any]):
        """Saves a new preset to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO presets (type, name, content_json) VALUES (?, ?, ?)",
                (preset_type, name, json.dumps(content))
            )
            conn.commit()

    def get_presets(self, preset_type: str) -> List[Dict[str, Any]]:
        """Retrieves all presets of a specific type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM presets WHERE type = ? ORDER BY created_at DESC", (preset_type,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_preset(self, preset_id: int):
        """Deletes a preset by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
            conn.commit()

    def get_preset_content(self, preset_id: int) -> Optional[Dict[str, Any]]:
        """Gets the content of a specific preset."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT content_json FROM presets WHERE id = ?", (preset_id,))
            row = cursor.fetchone()
            return json.loads(row["content_json"]) if row else None
