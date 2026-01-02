import pandas as pd
from typing import List, Dict, Any, Optional
from openai import OpenAI

from core.director.script_generator import ScriptGenerator
from core.director.crew_script_generator import CrewScriptGenerator
from core.director.world_builder import WorldBuilder
from core.director.crew_world_builder import CrewWorldBuilder
from core.director.casting_logic import CastingLogic
from core.director.crew_casting import CrewCastingDirector
from core.director.director_chat import DirectorChat
from core.director.crew_critic import CrewCritic
from core.director.crew_post_scene import CrewPostSceneAnalyst

class Director:
    """
    Facade class that delegating tasks to specialized director modules.
    Maintains compatibility with existing code while providing enhanced features.
    """
    def __init__(self, client: OpenAI, model_name: str, rag_engine: Optional[Any] = None):
        self._client = client
        self._modelName = model_name
        self._rag_engine = rag_engine
        
        # Sub-modules
        # Upgrade: Use CrewAI Generator for all components
        self._generator = CrewScriptGenerator(client, model_name)
        self._builder = CrewWorldBuilder(client, model_name)
        self._caster = CrewCastingDirector(client, model_name)
        self._chat = DirectorChat(client, model_name)
        self._critic = CrewCritic(client, model_name)
        self._analyst = CrewPostSceneAnalyst(client, model_name)

    def generate_script_with_constraints(self, topic: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        context_str = ""
        if self._rag_engine:
            results = self._rag_engine.query(topic, top_k=3)
            if results:
                context_str = "\n---\n".join(results)
        return self._generator.generate(topic, constraints, context_materials=context_str)

    def generate_random_theme(self, genre: str, reality: str, stage: str = "聊天群聊") -> str:
        return self._generator.generate_theme(genre, reality, stage)

    def generate_world_bible(self, topic: str, script_df: pd.DataFrame, stage: str) -> Dict[str, str]:
        return self._builder.build(topic, script_df, stage)

    def auto_casting(self, theme: str, actors_list: List[str], stage: str, scenario_df: pd.DataFrame = None, user_deep_participation: bool = False) -> List[Dict[str, Any]]:
        return self._caster.assign_roles(theme, actors_list, stage, scenario_df, user_deep_participation)

    def consult(self, history: List[Dict], current_script: List[Dict]) -> Dict[str, Any]:
        return self._chat.consult(history, current_script)

    def review_script(self, script_data: Dict[str, Any], topic: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        New capability: In-depth script review using CrewCritic.
        """
        return self._critic.review(script_data, topic, constraints)

    def analyze_scene(self, chat_history: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        New capability: Post-scene analysis using CrewPostSceneAnalyst.
        """
        return self._analyst.analyze(chat_history, context)
