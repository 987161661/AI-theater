import json
import re
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from core.utils.json_parser import JSONParser, CastingModel, PersonaModel

logger = logging.getLogger("CastingLogic")

class CastingLogic:
    """
    Handles automatic role assignment and persona generation for actors.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    def assign_roles(self, theme: str, actors_list: List[str], stage: str, scenario_df: Any = None) -> Dict[str, Any]:
        """
        Phase 1: Assign a role and nickname to each actor.
        """
        scenario_text = scenario_df.to_markdown(index=False) if scenario_df is not None else "无详细剧本"
        
        prompt = (
            f"你现在是【总导演】。\n"
            f"演员名单：{', '.join(actors_list)}\n"
            f"剧本主题：{theme}\n"
            f"舞台设定：{stage}\n\n"
            f"【参考剧本时间线】\n{scenario_text}\n\n"
            "任务：为每位演员分配角色。\n"
            "输出 JSON 格式，结构如下：\n"
            "```json\n"
            "{\n"
            "  \"roles\": {\n"
            "    \"model_id_1\": {\"role\": \"角色名\", \"nickname\": \"群称呼\", \"brief\": \"一句话简介\"},\n"
            "    ...\n"
            "  }\n"
            "}\n"
            "```\n"
            "直接输出 JSON，不要多余解释。"
        )

        try:
            response = self._query(prompt)
            data = JSONParser.parse(response, CastingModel)
            if data:
                return {mid: role.model_dump() for mid, role in data.roles.items()}
            return {mid: {"role": "路人", "nickname": mid, "brief": "普通角色"} for mid in actors_list}
        except Exception as e:
            logger.error(f"Casting Error: {e}")
            return {mid: {"role": "路人", "nickname": mid, "brief": "普通角色"} for mid in actors_list}

    def generate_persona(self, model_id: str, role_info: Dict[str, str], theme: str, bible: Dict[str, str], stage: str, all_nicknames: List[str]) -> Dict[str, Any]:
        """
        Phase 2: Generate detailed system prompt and initial memories for a specific actor.
        """
        role = role_info.get("role", "参与者")
        nickname = role_info.get("nickname", model_id)
        brief = role_info.get("brief", "")
        group_name = bible.get("group_name", "讨论组")
        world_bible = bible.get("world_bible", "")
        all_members = "、".join(all_nicknames)

        from core.stage.stage_rules import StageRules
        rules = StageRules(stage)
        stage_instr = rules.get_stage_instructions(nickname, all_members, group_name)

        prompt = (
            f"你现在是【总导演】。根据以下设定为演员 **{model_id}** 撰写系统提示词。\n\n"
            f"【剧本主题】: {theme}\n"
            f"【统一世界观】: {world_bible}\n"
            f"【你的角色】: {role} (昵称: {nickname})\n"
            f"【背景简介】: {brief}\n\n"
            f"{stage_instr}\n"
            "任务：确定角色的目标和说话习惯。输出 JSON，包含 'system_prompt' 和 'initial_memories' (列表)。\n"
            "直接输出 JSON。"
        )

        try:
            response = self._query(prompt)
            data = JSONParser.parse(response, PersonaModel)
            if data:
                return data.model_dump()
            return {"system_prompt": f"你是{nickname}...", "initial_memories": [brief]}
        except Exception as e:
            logger.error(f"Persona Generation Error: {e}")
            return {"system_prompt": f"你是{nickname}...", "initial_memories": [brief]}

    def _query(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
