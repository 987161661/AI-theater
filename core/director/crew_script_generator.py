import os
import logging

# Disable CrewAI Telemetry and OpenTelemetry forcefully before import
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Agent, Task, Crew, LLM, Process
import pandas as pd
from typing import Dict, Any, List
from core.utils.json_parser import ScriptModel, ScriptEventModel
from openai import OpenAI
import os
import uuid
import random

logger = logging.getLogger("CrewScriptGenerator")

class CrewScriptGenerator:
    """
    CrewAI-powered script generator.
    Replaces the traditional ScriptGenerator with a multi-agent system.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self.model_name = model_name
        # Extract credentials from the OpenAI client
        self.api_key = client.api_key
        self.base_url = str(client.base_url)
        
        # Initialize the LLM for CrewAI
        # Force 'openai/' prefix to ensure CrewAI uses the OpenAI client (compatible with OpenRouter, DeepSeek, etc.)
        # instead of trying to load native providers (like Google/Anthropic) based on model name strings.
        llm_model = self.model_name
        if not llm_model.startswith("openai/"):
             llm_model = f"openai/{llm_model}"

        print(f"DEBUG: Initializing CrewAI LLM with Model: {llm_model}, Base URL: {self.base_url}")

        self.llm = LLM(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url
        )

    def generate(self, topic: str, constraints: Dict[str, Any], context_materials: str = "") -> pd.DataFrame:
        """
        Generates a script using a Writer and Reviewer agent crew.
        """
        genre = constraints.get("genre", "随机")
        reality = constraints.get("reality", "艺术现实")
        min_events = constraints.get("min_events", 3)
        max_events = constraints.get("max_events", 6)
        stage = constraints.get("stage", "聊天群聊")

        # 1. Define Agents
        screenwriter = Agent(
            role="资深编剧 (Senior Screenwriter)",
            goal="创作极具张力、逻辑严密且符合舞台设定的剧本",
            backstory=(
                "你是一位经验丰富的剧本作家，擅长在有限的场景（如聊天室、法庭）中构建扣人心弦的故事。"
                "你精通通过对话和微小的事件推动剧情，善于埋下伏笔和制造反转。"
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

        editor = Agent(
            role="剧本主编 (Script Editor)",
            goal="审核剧本的逻辑性、格式合规性以及戏剧冲突",
            backstory=(
                "你是一位严苛的剧本主编。你的眼睛容不下任何逻辑漏洞。"
                "你负责确保剧本不仅精彩，而且结构清晰，每个事件都有明确的时间、内容和收敛目标。"
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

        # 2. Define Tasks
        # Task 1: Draft the script structure
        draft_task = Task(
            description=(
                f"请构思一个剧本的大纲框架。\n"
                f"【主题】: {topic}\n"
                f"【流派】: {genre}\n"
                f"【世界观】: {reality}\n"
                f"【舞台】: {stage}\n"
                f"【参考素材 (RAG)】: {context_materials if context_materials else '无'}\n"
                f"【篇幅】: {min_events} - {max_events} 幕\n\n"
                f"【核心任务】:\n"
                f"1. 设定一个引人入胜的【开场事件】(Act 1)。必须包含：明确的时间点、建群/聚会的原因、核心矛盾的触发点。\n"
                f"   **特别注意**：Act 1 必须像后续幕一样，仅作为一个独立的、单一的时间线节点存在，严禁将其拆分为多个子步骤。\n"
                f"2. 规划后续的【起承转合】阶段 (Act 2, Act 3, Act 4)，但**不要**填充具体内容，仅保留阶段性目标（如“矛盾升级”、“高潮爆发”、“结局收束”）。\n"
                f"3. 后续每一幕的内容将由【现场导演】根据演员的实际发挥实时生成，所以这里只需要搭建骨架。\n"
            ),
            expected_output="一份包含4个阶段（起承转合）的剧本大纲，其中第一幕非常详细，后续幕仅为框架。",
            agent=screenwriter
        )

        # Task 2: Refine and Format
        refine_task = Task(
            description=(
                "将编剧的大纲整理为结构化数据。\n"
                "1. 第一幕 (The Setup): 必须包含详细的 Time, Event (背景描述), Goal。\n"
                "2. 后续幕 (Development/Climax/Resolution): Time 填 'TBD', Event 填 '待定 (由导演实时生成)', Goal 填该阶段的宏观目标。\n"
                "3. 严格遵守 ScriptModel 格式。"
            ),
            expected_output="符合 ScriptModel 结构的 JSON 数据。",
            agent=editor,
            context=[draft_task],
            output_pydantic=ScriptModel
        )

        # 3. Create Crew
        crew = Crew(
            agents=[screenwriter, editor],
            tasks=[draft_task, refine_task],
            process=Process.sequential,
            verbose=True,
            cache=False
        )

        # 4. Kickoff
        try:
            result = crew.kickoff()
            
            # Extract data
            final_data = None
            if hasattr(result, "pydantic") and result.pydantic:
                final_data = result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                try:
                    final_data = ScriptModel(**result.json_dict)
                except Exception:
                    pass

            if not final_data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                final_data = JSONParser.parse(result.raw, ScriptModel)
            
            if final_data:
                return self._to_dataframe(final_data)
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"CrewAI Execution Error: {e}")
            return pd.DataFrame()

    def adapt_script(self, history_summary: str, current_plan: Dict[str, str], theme: str, available_cast: List[str] = None) -> Dict[str, str]:
        """
        Adapts the next event using a World Architect agent.
        """
        cast_str = ", ".join(available_cast) if available_cast else "Unknown"
        
        live_director = Agent(
            role="世界构建者 (World Architect)",
            goal="根据上一幕的剧情结果，推进世界时间线并设定下一幕背景",
            backstory=(
                "你是整个AI剧场的幕后推手。你的工作不是写台词，而是构建‘舞台’和‘时间’。"
                "上一幕刚刚结束，你需要根据演员们的表现（Summary），决定世界发生了什么变化。"
                "你需要设定下一幕的【时间点】（例如：‘三个月后’，‘第二天清晨’）和【背景事件】（例如：‘MIAOBAO进化失败，变得暴躁’）。"
                "你的目标是推动故事完成‘起承转合’的闭环。"
            ),
            llm=self.llm,
            verbose=True
        )

        task = Task(
            description=(
                f"【剧本主题】: {theme}\n"
                f"【可用演员】: {cast_str}\n"
                f"【上一幕总结】: {history_summary}\n"
                f"【当前阶段目标】: {current_plan.get('Goal', '推进剧情')}\n\n"
                f"任务：\n"
                f"1. 分析上一幕的总结。角色们达成了什么？情绪如何？\n"
                f"2. 规划下一幕的【时间跳跃】。故事应该过去多久？\n"
                f"3. 设定下一幕的【背景事件】。世界发生了什么变化？是否有突发新闻？\n"
                f"4. 设定下一幕的【总体目标】。\n"
                f"5. 输出结构化数据 (Time, Event, Goal)。\n"
                f"   - Time: 新的时间点。\n"
                f"   - Event: 详细的背景描述（给演员看的Context）。\n"
                f"   - Goal: 本幕的引导性目标。"
            ),
            expected_output="下一幕的结构化数据 (Time, Event, Goal)。",
            agent=live_director,
            output_pydantic=ScriptEventModel
        )

        crew = Crew(
            agents=[live_director],
            tasks=[task],
            verbose=True
        )

        try:
            result = crew.kickoff()
            event_data = result.pydantic
            if not event_data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                event_data = JSONParser.parse(result.raw, ScriptEventModel)
            
            if event_data:
                return event_data.model_dump()
            return current_plan
        except Exception as e:
            print(f"CrewAI Adapt Error: {e}")
            return current_plan

    def generate_themes(self, genre: str, reality: str, stage: str = "聊天群聊", count: int = 1) -> List[str]:
        """
        Uses a Creative Director agent to brainstorm multiple themes.
        """
        # Create a high-temperature LLM for maximum creativity
        creative_llm = LLM(
            model=self.llm.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=1.0  # Max creativity
        )

        creative_director = Agent(
            role="创意总监 (Creative Director)",
            goal="构思一句话的文字交互剧本主题",
            backstory="你擅长用最简练的语言描述最吸引人的故事核心。",
            llm=creative_llm,
            verbose=True
        )

        themes = []
        # Create a single crew to handle multiple tasks (parallel if possible, but sequential is safer for now)
        # To ensure diversity, we create distinct tasks with different seeds
        
        tasks = []
        for i in range(count):
            random_seed = f"{uuid.uuid4()}-{random.randint(100000, 999999)}"
            logger.info(f"Theme Generation Seed [{i+1}/{count}]: {random_seed}")
            
            task = Task(
                description=(
                    f"根据以下设定，构思一个极具创意的主题。\n"
                    f"【流派】: {genre}\n"
                    f"【世界观】: {reality}\n"
                    f"【舞台形式】: {stage}\n"
                    f"Random Seed: {random_seed}\n"
                    "只输出一句话，不要包含引号或解释。确保主题适配舞台形式。\n"
                    "**重要约束**：字数严格控制在 40 字以内。"
                ),
                expected_output="一句话的主题（40字以内）。",
                agent=creative_director
            )
            tasks.append(task)

        crew = Crew(
            agents=[creative_director],
            tasks=tasks,
            verbose=True,
            cache=False
        )

        try:
            # Kickoff returns the result of the LAST task, so we need to inspect tasks output or run individually
            # CrewAI 0.x usually returns final output. We might need to iterate.
            # For simplicity and reliability, let's run them sequentially in a loop if we can't easily extract all.
            # Actually, let's run a loop of kickoffs to be safe and ensure total isolation.
            pass
        except Exception:
            pass
            
        # Re-implementation: Loop to ensure we get a list
        # Re-using the agent is fine.
        
        final_results = []
        for i in range(count):
            random_seed = f"{uuid.uuid4()}-{random.randint(100000, 999999)}"
            logger.info(f"Theme Generation Seed [{i+1}/{count}]: {random_seed}")
            print(f"Theme Generation Seed [{i+1}/{count}]: {random_seed}", flush=True)
            t = Task(
                description=(
                    f"根据以下设定，构思一个极具创意的主题。\n"
                    f"【流派】: {genre}\n"
                    f"【世界观】: {reality}\n"
                    f"【舞台形式】: {stage}\n"
                    f"Random Seed: {random_seed}\n"
                    "只输出一句话，不要包含引号或解释。确保主题适配舞台形式。\n"
                    "**重要约束**：字数严格控制在 40 字以内。"
                ),
                expected_output="一句话的主题（40字以内）。",
                agent=creative_director
            )
            c = Crew(agents=[creative_director], tasks=[t], verbose=True, cache=False)
            res = c.kickoff()
            theme_str = str(res).strip().replace('"', '').replace('“', '').replace('”', '')
            final_results.append(theme_str)
            
        return final_results

    def generate_theme(self, genre: str, reality: str, stage: str = "聊天群聊") -> str:
        # Backward compatibility wrapper
        return self.generate_themes(genre, reality, stage, 1)[0]

    def _to_dataframe(self, sc_data: ScriptModel) -> pd.DataFrame:
        events_list = [e.model_dump() for e in sc_data.events]
        if not events_list:
            return pd.DataFrame()
            
        df = pd.DataFrame(events_list)
        for col in ["Time", "Event", "Goal"]:
            if col not in df.columns:
                df[col] = ""
        
        if "Selected" not in df.columns:
            df.insert(0, "Selected", False)
        if not df.empty:
            df.at[0, "Selected"] = True
        return df
