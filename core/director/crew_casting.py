from crewai import Agent, Task, Crew, LLM
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import pandas as pd
from openai import OpenAI
import logging

logger = logging.getLogger("CrewCasting")

# Define Pydantic models for structured output
class SuggestedRole(BaseModel):
    role: str = Field(description="Formal role name (e.g., Detective, Narrator)")
    nickname: str = Field(description="Stage-specific nickname or ID")
    brief: str = Field(description="Character personality and background summary")
    source_type: str = Field(description="Performance source: 'User', 'Script', or 'AI'")

class SuggestedCasting(BaseModel):
    suggested_roles: List[SuggestedRole] = Field(description="List of suggested roles")

class PersonaResult(BaseModel):
    system_prompt: str = Field(description="The system prompt for the AI actor")
    initial_memories: List[str] = Field(description="List of initial memories for the actor")

class ScriptConfigResult(BaseModel):
    type: str = Field(description="Trigger type: '定时发送' (Scheduled), '关键词触发' (Keyword), or '特定场景' (Scene)")
    condition: str = Field(description="Specific trigger condition (e.g. '10:00' or 'hello')")
    text: str = Field(description="Text to send when triggered")

class CrewCastingDirector:
    def __init__(self, client: OpenAI, model_name: str):
        self.model_name = model_name
        self.api_key = client.api_key
        self.base_url = str(client.base_url)
        
        llm_model = self.model_name
        if self.base_url and "openai" not in llm_model and "/" not in llm_model:
             llm_model = f"openai/{llm_model}"

        self.llm = LLM(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url
        )

    def assign_roles(self, theme: str, actors_list: List[str], stage: str, scenario_df: Any = None, user_deep_participation: bool = False) -> List[Dict[str, Any]]:
        """
        Uses a Casting Director agent to suggest roles.
        """
        try:
            scenario_text = "No detailed script"
            if scenario_df is not None:
                if isinstance(scenario_df, pd.DataFrame):
                    scenario_text = scenario_df.to_markdown(index=False)
                else:
                    scenario_text = str(scenario_df)

            if user_deep_participation:
                participation_desc = "用户希望【深度参与】(Deep Participation)，担任核心主角之一，戏份吃重。"
            else:
                participation_desc = "用户希望【客串围观】(Cameo/Spectator)，只担任边缘路人甲，戏份极少，主要负责围观和偶尔插话，绝不承担推动剧情的任务。"

            casting_director = Agent(
                role="选角导演 (Casting Director)",
                goal="根据剧本主题和舞台设定，挑选最合适的角色阵容",
                backstory=(
                    "你是一位慧眼独具的选角导演。你擅长根据剧本的冲突需求，设计出性格鲜明、功能互补的角色阵容。"
                    "你特别注意不同舞台（如微信群、法庭、跑团）对角色昵称和说话方式的特殊要求。"
                ),
                llm=self.llm,
                verbose=True
            )

            task_description = (
                f"【剧本主题】: {theme}\n"
                f"【舞台设定】: {stage}\n"
                f"【用户偏好】: {participation_desc}\n"
                f"【剧本大纲】:\n{scenario_text}\n\n"
                f"任务要求:\n"
                f"1. 构思 3-5 个角色。\n"
                f"2. 必须包含一个用户(User)角色。**特别注意**：如果用户选择客串，请务必将其设定为背景板角色（如吃瓜群众），不要安排任何关键剧情任务。\n"
                f"3. 必须包含一个旁白或系统(Script)角色。\n"
                f"4. 其余为AI角色，负责推动剧情。\n"
                f"5. 根据舞台设定生成合适的【昵称】:\n"
                f"   - 微信群: 真实网名 (e.g., 'A01建材王总', 'momo')\n"
                f"   - 法庭: 职务名 (e.g., '审判长', '原告')\n"
                f"   - 跑团: 名字/职业\n"
            )

            task = Task(
                description=task_description,
                expected_output="A JSON object containing a list of suggested roles.",
                agent=casting_director,
                output_pydantic=SuggestedCasting
            )

            crew = Crew(
                agents=[casting_director],
                tasks=[task],
                verbose=True
            )

            result = crew.kickoff()
            
            # Debug logging
            logger.info(f"Crew Casting Result Raw: {result.raw}")
            print(f"DEBUG: Crew Casting Result Raw: {result.raw}")

            # Extract data
            data = None
            if hasattr(result, "pydantic") and result.pydantic:
                data = result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                # Try to parse from json_dict if pydantic is missing but json is present
                try:
                    data = SuggestedCasting(**result.json_dict)
                except Exception as parse_err:
                    logger.warning(f"Failed to parse json_dict: {parse_err}")

            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, SuggestedCasting)
            
            if data and data.suggested_roles:
                return [role.model_dump() for role in data.suggested_roles]
            
            # Fallback if empty
            logger.warning("Crew Casting returned empty data.")
            return []

        except Exception as e:
            logger.error(f"Crew Casting Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def generate_persona(self, model_id: str, role_info: Dict[str, str], theme: str, bible: Dict[str, str], stage: str, all_nicknames: List[str]) -> Dict[str, Any]:
        """
        Uses a Persona Psychologist agent to generate detailed actor persona.
        """
        try:
            role = role_info.get("role", "Participant")
            nickname = role_info.get("nickname", model_id)
            brief = role_info.get("brief", "")
            group_name = bible.get("group_name", "Group")
            world_bible = bible.get("world_bible", "")
            all_members_str = ", ".join(all_nicknames)

            from core.stage.stage_rules import StageRules
            rules = StageRules(stage)
            stage_instr = rules.get_stage_instructions(nickname, all_members_str, group_name)

            psychologist = Agent(
                role="角色心理侧写师 (Persona Psychologist)",
                goal="构建深度的角色内心世界和行为准则",
                backstory=(
                    "你不仅是编剧，更是心理学家。你擅长为虚拟角色注入灵魂，通过System Prompt定义他们的说话风格、思维模式和核心动机。"
                    "你明白'Show, Don't Tell'的原则，你会指示演员如何行动，而不是仅仅描述他们是谁。"
                ),
                llm=self.llm,
                verbose=True
            )

            task_desc = (
                f"为角色生成 System Prompt 和 初始记忆。\n\n"
                f"【角色档案】\n"
                f"- 姓名: {role}\n"
                f"- 昵称/ID: {nickname}\n"
                f"- 简介: {brief}\n"
                f"- 剧本主题: {theme}\n"
                f"- 世界观: {world_bible}\n\n"
                f"【舞台规则(必须遵守)】:\n{stage_instr}\n\n"
                f"任务要求:\n"
                f"1. 编写一段高质量的 System Prompt (第二人称 '你')。\n"
                f"2. 包含 3-5 条初始记忆 (Initial Memories)。\n"
                f"3. 严禁出现 '你现在是导演' 等出戏指令。\n"
            )

            task = Task(
                description=task_desc,
                expected_output="A JSON object with system_prompt and initial_memories.",
                agent=psychologist,
                output_pydantic=PersonaResult
            )

            crew = Crew(
                agents=[psychologist],
                tasks=[task],
                verbose=True
            )

            result = crew.kickoff()
            
            # Extract data
            data = None
            if hasattr(result, "pydantic") and result.pydantic:
                data = result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                try:
                    data = PersonaResult(**result.json_dict)
                except Exception:
                    pass

            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, PersonaResult)

            if data:
                return data.model_dump()
            
            # Fallback
            return {
                "system_prompt": f"你是{nickname}。{brief}",
                "initial_memories": [f"我是{nickname}", brief]
            }

        except Exception as e:
            logger.error(f"Crew Persona Error: {e}")
            return {
                "system_prompt": f"你是{nickname}。{brief}",
                "initial_memories": [f"我是{nickname}", brief]
            }

    def generate_script_config(self, role_info: Dict[str, str], theme: str, bible: Dict[str, str]) -> Dict[str, Any]:
        """
        Uses an Automation Specialist agent to configure script bots.
        """
        try:
            role = role_info.get("role", "ScriptBot")
            nickname = role_info.get("nickname", role)
            brief = role_info.get("brief", "")
            
            automation_specialist = Agent(
                role="自动化配置专家 (Automation Specialist)",
                goal="为脚本角色配置精确的触发逻辑",
                backstory="你精通自动化脚本的逻辑设计，能够根据角色功能设计最合理的触发条件和台词。",
                llm=self.llm,
                verbose=True
            )

            task_desc = (
                f"为脚本角色生成配置。\n"
                f"角色: {role} ({nickname})\n"
                f"简介: {brief}\n"
                f"情境: {theme}\n\n"
                f"任务要求:\n"
                f"1. 确定触发类型 (type): '定时发送', '关键词触发', 或 '特定场景'。\n"
                f"2. 设定条件 (condition)。\n"
                f"3. 撰写台词 (text)。\n"
            )

            task = Task(
                description=task_desc,
                expected_output="A JSON object with type, condition, and text.",
                agent=automation_specialist,
                output_pydantic=ScriptConfigResult
            )

            crew = Crew(
                agents=[automation_specialist],
                tasks=[task],
                verbose=True
            )

            result = crew.kickoff()
            
            data = result.pydantic
            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, ScriptConfigResult)
            
            if data:
                return data.model_dump()

            return {
                "type": "定时发送",
                "condition": "Day 1 09:00",
                "text": f"大家好，我是{nickname}。"
            }

        except Exception as e:
            logger.error(f"Crew ScriptConfig Error: {e}")
            return {
                "type": "定时发送",
                "condition": "Day 1 09:00",
                "text": f"大家好，我是{nickname}。"
            }

