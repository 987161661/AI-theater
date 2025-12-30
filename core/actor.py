import pandas as pd
from typing import List, Dict, Any, Optional
from openai import OpenAI

from core.actor.base_actor import Actor
from core.actor.persona_factory import PersonaFactory
from core.actor.memory_bank import MemoryBank

class CastingDirector:
    """
    Facade class for all casting and persona generation tasks.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name
        self._factory = PersonaFactory(client, model_name)

    def extract_characters(self, script_df: pd.DataFrame) -> List[str]:
        if "Characters" not in script_df.columns:
            return []
        
        chars = set()
        for item in script_df["Characters"].dropna():
            parts = str(item).replace(";", ",").split(",")
            for p in parts:
                p = p.strip()
                if p and p.lower() not in ["none", "n/a"]:
                    chars.add(p)
        return list(sorted(chars))

    def generate_persona(self, char_info: Dict, script_df: pd.DataFrame, 
                         stage_type: str, world_bible: Dict, 
                         all_nicknames: List[str]) -> Dict[str, Any]:
        
        script_summary = script_df.to_string(index=False)
        return self._factory.create_persona(
            char_info, script_summary, stage_type, world_bible, all_nicknames
        )

# Export Actor for convenience
__all__ = ["Actor", "CastingDirector", "MemoryBank"]
