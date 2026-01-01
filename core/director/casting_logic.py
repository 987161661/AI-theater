import json
import re
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai

from core.utils.json_parser import JSONParser, CastingModel, PersonaModel

logger = logging.getLogger("CastingLogic")

class CastingLogic:
    """
    Handles automatic role assignment and persona generation for actors.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.APIStatusError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5)
    )
    def _query(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content

    def assign_roles(self, theme: str, actors_list: List[str], stage: str, scenario_df: Any = None, user_deep_participation: bool = False) -> List[Dict[str, Any]]:
        """
        Phase 1: Suggest dynamic roles and performer types (AI, Script, User).
        """
        try:
            # Safe markdown conversion with fallback
            try:
                scenario_text = scenario_df.to_markdown(index=False) if scenario_df is not None else "无详细剧本"
            except Exception as e:
                logger.warning(f"Markdown conversion failed: {e}, using CSV format")
                scenario_text = scenario_df.to_csv(index=False) if scenario_df is not None else "无详细剧本"
            
            participation_status = "深度参与(作为核心主角,分配关键剧情目标)" if user_deep_participation else "普通客串(分配边缘角色,可选参与)"

            prompt = (
                "你现在是【AI剧场总导演】。\n"
                "剧本主题:" + theme + "\n"
                "舞台设定:" + stage + "\n"
                "用户参与偏好:" + participation_status + "\n\n"
                "【参考剧本时间线】\n" + scenario_text + "\n\n"
                "任务:根据剧本内容,构思出 3-5 个合理的角色列表。并根据其职能建议【表演来源】(source_type)。\n\n"
                "【特定舞台ID规范】(IMPORTANT):\n"
                "角色包含“正式角色名”(如: 张伟) 和 “舞台特定ID/昵称”(如: 孤独的风).\n"
                "请根据【舞台设定】生成极具特色的昵称:\n"
                "- 如果是【聊天群聊/微信】: 必须生成真实的微信昵称。可以使用 Emoji，可以是网名，不要直接用真名(除非这是工作群)。例如: 'AAA建材王总', '水晶男孩', 'Sherlock 🕵️', 'momo'.\n"
                "- 如果是【跑团桌】: 使用 '角色名/职业' 格式，或符合D&D风格的名字。\n"
                "- 如果是【法庭】: 使用 '原告-张三', '审判长' 等职务格式。\n"
                "- 如果是【辩论赛】: 使用 '正方一辩', '反方二辩' 等。\n\n"
                "表演来源规则:\n"
                "1. User: 必须且仅包含一个建议给用户的角色。根据偏好决定其重要性。\n"
                "2. Script: 适用于旁白、任务发放者、具有固定台词逻辑的系统 NPC 等。\n"
                "3. AI: 适用于剧中的核心互动角色、反派、或具有自由思考能力的 NPC。\n\n"
                "请严格输出以下结构的 JSON(不要包含多余文字):\n"
                "```json\n"
                "{\n"
                '  "suggested_roles": [\n'
                "    {\n"
                '      "role": "正式角色名 (如: 李明, 旁白)",\n'
                '      "nickname": "舞台特定ID/昵称 (如: 明明不是我 🌚, System)",\n'
                '      "brief": "角色性格与背景说明",\n'
                '      "source_type": "AI" \n'
                "    }\n"
                "  ]\n"
                "}\n"
                "```"
            )

            response = self._query(prompt)
            
            # Try structured parsing first
            from pydantic import BaseModel
            class SuggestedRole(BaseModel):
                role: str
                nickname: str
                brief: str
                source_type: str

            class SuggestedCasting(BaseModel):
                suggested_roles: List[SuggestedRole]

            data = JSONParser.parse(response, SuggestedCasting)
            if data and data.suggested_roles:
                result = [role.model_dump() for role in data.suggested_roles]
                # Ensure we have at least 3 roles
                if len(result) >= 3:
                    return result
            
            # Fallback: try manual JSON extraction
            try:
                json_match = re.search(r'\{[^}]+suggested_roles[^}]+\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if 'suggested_roles' in parsed and len(parsed['suggested_roles']) >= 3:
                        return parsed['suggested_roles']
            except:
                pass
            
            # Smart fallback based on theme and stage
            # REMOVED Fallback to allow error to surface
            # return self._generate_default_roles(theme, stage, user_deep_participation)
            return []
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ CastingLogic Error: {error_msg}")
            logger.error(f"Casting Suggestion Error: {error_msg}")
            # REMOVED Fallback to allow error to surface
            # return self._generate_default_roles(theme, stage, user_deep_participation)
            raise e

    def _generate_default_roles(self, theme: str, stage: str, user_deep_participation: bool) -> List[Dict[str, Any]]:
        """Generate intelligent default roles based on theme and stage."""
        user_role = {
            "role": "核心参与者" if user_deep_participation else "观察者",
            "nickname": "玩家",
            "brief": "主导剧情发展" if user_deep_participation else "旁观并适时参与",
            "source_type": "User"
        }
        
        narrator_role = {
            "role": "旁白",
            "nickname": "系统",
            "brief": "负责引导" + theme + "的剧情走向",
            "source_type": "Script"
        }
        
        ai_role = {
            "role": "核心角色",
            "nickname": "NPC",
            "brief": "在" + stage + "环境中与用户互动的AI角色",
            "source_type": "AI"
        }
        
        antagonist_role = {
            "role": "对立角色",
            "nickname": "反派",
            "brief": "为剧情制造冲突和张力",
            "source_type": "AI"
        }
        
        return [narrator_role, ai_role, antagonist_role, user_role]

    def generate_persona(self, model_id: str, role_info: Dict[str, str], theme: str, bible: Dict[str, str], stage: str, all_nicknames: List[str]) -> Dict[str, Any]:
        """
        Phase 2: Generate detailed system prompt and initial memories for a specific actor.
        """
        try:
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
                "你是一个专业的 Prompt Engineer。请根据以下设定，为 AI 演员撰写一段高质量的 System Prompt。\n\n"
                "【元数据】\n"
                f"- 剧本主题: {theme}\n"
                f"- 世界观背景: {world_bible}\n"
                f"- 角色名称: {role} (ID/昵称: {nickname})\n"
                f"- 角色简介: {brief}\n\n"
                "【必须包含的舞台指令】(请完整融入以确保行为规范):\n"
                f"{stage_instr}\n\n"
                "【任务要求】\n"
                "1. 输出一个 JSON 对象，包含 `system_prompt` 和 `initial_memories` (String List)。\n"
                "2. `system_prompt` 必须以第二人称 ('你') 撰写，直接告诉演员他是谁，他的目标是什么，以及如何说话。\n"
                "3. **严禁**在 `system_prompt` 中出现 '你现在是导演' 或 '以下是提示词' 等元指令。直接输出角色指令本身。\n"
                "4. 确保 `system_prompt` 中包含上述所有的【舞台指令】，尤其是 '交互规范' 和 '语言风格'。\n"
                "5. `initial_memories` 是该角色开始时就知道的关于世界或他人的秘密/事实。\n"
            )

            response = self._query(prompt)
            data = JSONParser.parse(response, PersonaModel)
            if data:
                return data.model_dump()
            
            # Fallback persona
            return {
                "system_prompt": f"你是{nickname}，在{group_name}中扮演{role}。\n\n{stage_instr}\n\n{brief}",
                "initial_memories": [f"我是{nickname}", brief, world_bible]
            }
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ Persona Generation Error: {error_msg}")
            logger.error(f"Persona Generation Error: {error_msg}")
            # Fallback with stage instructions even on error if possible
            try:
                from core.stage.stage_rules import StageRules
                rules = StageRules(stage)
                stage_instr = rules.get_stage_instructions(nickname, "、".join(all_nicknames), bible.get("group_name", "群聊"))
            except:
                stage_instr = ""
                
            return {
                "system_prompt": f"你是{nickname}。{brief}\n{stage_instr}",
                "initial_memories": [brief]
            }

    def generate_script_config(self, role_info: Dict[str, str], theme: str, bible: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate JSON configuration for a Script Robot.
        """
        try:
            role = role_info.get("role", "ScriptBot")
            nickname = role_info.get("nickname", role)
            brief = role_info.get("brief", "")
            
            prompt = (
                "你是一个自动化脚本配置助手。请根据以下角色设定，生成一个简单的脚本行为配置。\n\n"
                f"角色: {role} ({nickname})\n"
                f"简介: {brief}\n"
                f"当前情境: {theme}\n\n"
                "请生成一个 JSON 对象，包含以下字段：\n"
                "- `type`: 触发类型，必须是 ['定时发送', '关键词触发', '特定场景'] 之一。\n"
                "- `condition`: 触发具体条件 (如 '10:00' 或 '听到你好')。\n"
                "- `text`: 触发时发送的文本内容。\n\n"
                "如果是旁白，通常是 '定时发送' (开场) 或 '特定场景'。\n"
                "如果是任务NPC，可能是 '关键词触发'。\n"
                "只输出 JSON。"
            )
            
            response = self._query(prompt)
            
            # Use a simple dict parser or existing JSON parser if generic enough
            # We construct a temporary model or just parse raw json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                config = json.loads(json_match.group())
                # Validate fields
                if "type" in config and "text" in config:
                    return config
            
            # Fallback
            return {
                "type": "定时发送",
                "condition": "Day 1 09:00",
                "text": f"大家好，我是{nickname}。{brief}"
            }
        except Exception as e:
            logger.error(f"Script Config Generation Error: {e}")
            return {
                "type": "定时发送",
                "condition": "Day 1 09:00",
                "text": f"大家好，我是{nickname}。"
            }

