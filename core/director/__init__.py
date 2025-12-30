import pandas as pd
from typing import List, Dict, Any, Optional
from openai import OpenAI

from core.director.script_generator import ScriptGenerator
from core.director.world_builder import WorldBuilder
from core.director.casting_logic import CastingLogic
from core.director.director_chat import DirectorChat

class Director:
    """
    Facade class that delegating tasks to specialized director modules.
    Maintains compatibility with existing code while providing enhanced features.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name
        
        # Sub-modules
        self._generator = ScriptGenerator(client, model_name)
        self._builder = WorldBuilder(client, model_name)
        self._caster = CastingLogic(client, model_name)
        self._chat = DirectorChat(client, model_name)

    def generate_script_with_constraints(self, topic: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        return self._generator.generate(topic, constraints)

    def generate_world_bible(self, topic: str, script_df: pd.DataFrame, stage: str) -> Dict[str, str]:
        return self._builder.build(topic, script_df, stage)

    def auto_casting(self, theme: str, actors_list: List[str], stage: str) -> Dict[str, Any]:
        return self._caster.assign_roles(theme, actors_list, stage)

    def consult(self, history: List[Dict], current_script: List[Dict]) -> Dict[str, Any]:
        return self._chat.consult(history, current_script)
