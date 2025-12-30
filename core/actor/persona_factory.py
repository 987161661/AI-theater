from typing import Dict, List, Any
from openai import OpenAI
from core.utils.json_utils import extract_json
from core.utils.prompt_templates import get_stage_directives

class PersonaFactory:
    """
    Generates detailed personas (System Prompt + Memories) based on stage and context.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    def create_persona(self, char_info: Dict, script_summary: str, 
                       stage_type: str, world_bible: Dict, 
                       all_nicknames: List[str]) -> Dict[str, Any]:
        
        group_name = world_bible.get("group_name", "Stage")
        bible_text = world_bible.get("world_bible", "")
        nickname = char_info.get("nickname", char_info["name"])
        
        # Get specialized stage instructions
        context = {
            "nickname": nickname,
            "group_name": group_name,
            "members": "、".join(all_nicknames)
        }
        stage_directives = get_stage_directives(stage_type, context)

        prompt = f"""
        Role: Casting Director.
        Action: Create a deep persona for actor "{char_info['name']}" (AS "{nickname}").
        
        [World Facts]
        {bible_text}
        
        [Script Overview]
        {script_summary}
        
        [Brief]
        {char_info.get('brief', 'A character in the play.')}
        
        [Stage Rules]
        {stage_directives}
        
        Output JSON:
        {{
            "system_prompt": "Direct instructions to the model (You are...)",
            "initial_memories": ["Fact 1", "Self-secret 2", ...]
        }}
        """

        try:
            response = self._client.chat.completions.create(
                model=self._modelName,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            return extract_json(response.choices[0].message.content) or {}
        except Exception as e:
            print(f"Persona Generation Error: {e}")
            return {"system_prompt": f"You are {nickname}.", "initial_memories": []}
