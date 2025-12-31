import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from core.state.db_manager import DBManager

class StateManager:
    """
    Centralized management for application state.
    Wraps Streamlit session_state to provide structured access.
    """
    db = DBManager()
    
    @staticmethod
    def initialize():
        """Ensure all required session state keys exist."""
        # Load configs from DB if they exist
        saved_configs = StateManager.db.load_providers()
        
        defaults = {
            "llm_configs": saved_configs if saved_configs else [],
            "director_chat_history": [],
            "world_bible": {},
            "current_script": None, # Previous script (for backward compat)
            "scenario_df": pd.DataFrame(), # New structure
            "scenario_theme": "一场发生在封闭空间内的心理博弈",
            "casting_data": [],
            "actors_config": {},
            
            # === 新数据结构：角色为中心 ===
            "actor_personas": {},  # Key: actor_id, Value: {model_id, role, nickname, prompt, memories, ...}
            
            # === 旧数据结构：保留以向后兼容 ===
            "nicknames": {},
            "custom_prompts": {},
            "custom_memories": {},
            
            "current_stage_type": "聊天群聊",
            "prompt_version": 0,
            "director_phase": "idle" # idle, reviewing, finalized
        }
        for key, val in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = val
        
        # Ensure scenario_df is always a DataFrame
        if not isinstance(st.session_state.scenario_df, pd.DataFrame):
            st.session_state.scenario_df = pd.DataFrame()

    @property
    def llm_configs(self) -> List[Dict]:
        return st.session_state.get("llm_configs", [])

    @property
    def world_bible(self) -> Dict:
        return st.session_state.get("world_bible", {})

    def set_world_bible(self, bible: Dict):
        st.session_state.world_bible = bible

    def increment_prompt_version(self):
        st.session_state.prompt_version += 1

    @property
    def prompt_version(self) -> int:
        return st.session_state.get("prompt_version", 0)

# Singleton-like instance access
state_manager = StateManager()
