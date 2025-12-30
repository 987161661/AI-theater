import json
import re
from typing import List, Dict, Any, Type, TypeVar, Optional
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger("JSONParser")

T = TypeVar("T", bound=BaseModel)

class ScriptEventModel(BaseModel):
    Time: str
    Event: str
    Goal: str
    Location: Optional[str] = "默认地点"
    Characters: Optional[str] = ""

class ScriptModel(BaseModel):
    theme: str
    events: List[ScriptEventModel]

class RoleInfoModel(BaseModel):
    role: str
    nickname: str
    brief: str

class CastingModel(BaseModel):
    roles: Dict[str, RoleInfoModel]

class WorldBibleModel(BaseModel):
    group_name: str
    world_bible: str

class PersonaModel(BaseModel):
    system_prompt: str
    initial_memories: List[str]

class JSONParser:
    """
    Utility to robustly parse and validate JSON from LLM responses.
    Supports markdown code blocks and raw JSON strings.
    """
    @staticmethod
    def parse(text: str, model_class: Type[T]) -> Optional[T]:
        # 1. Try to extract JSON from markdown blocks
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            candidate = json_match.group(1).strip()
        else:
            # 2. Try to find anything between { and }
            json_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if json_match:
                candidate = json_match.group(0).strip()
            else:
                candidate = text.strip()

        try:
            data = json.loads(candidate)
            return model_class(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse/validate JSON for {model_class.__name__}: {e}")
            logger.debug(f"Candidate text: {candidate}")
            return None

    @staticmethod
    def force_parse_list(text: str, model_class: Type[T]) -> List[T]:
        """Special handling for list responses."""
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return []
        
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, list):
                return [model_class(**item) for item in data]
            return []
        except:
            return []
