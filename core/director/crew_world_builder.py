from crewai import Agent, Task, Crew, LLM
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import pandas as pd
from openai import OpenAI
import logging

logger = logging.getLogger("CrewWorldBuilder")

class WorldBibleOutput(BaseModel):
    group_name: str = Field(description="Creative name for the group/chat room")
    world_bible: str = Field(description="Comprehensive world setting, rules, and common knowledge")

class CrewWorldBuilder:
    def __init__(self, client: OpenAI, model_name: str, rag_engine: Any = None):
        self.model_name = model_name
        self.api_key = client.api_key
        self.base_url = str(client.base_url)
        self.rag_engine = rag_engine
        
        llm_model = self.model_name
        if self.base_url and "openai" not in llm_model and "/" not in llm_model:
             llm_model = f"openai/{llm_model}"

        self.llm = LLM(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url
        )

    def build(self, topic: str, script_df: pd.DataFrame, stage: str) -> Dict[str, str]:
        """
        Uses a World Architect agent to build the world bible.
        """
        try:
            scenario_text = "No detailed script"
            if isinstance(script_df, pd.DataFrame):
                try:
                    scenario_text = script_df.to_markdown(index=False)
                except:
                    scenario_text = script_df.to_csv(index=False)
            
            rag_context = ""
            if self.rag_engine:
                try:
                    context_list = self.rag_engine.query(topic, top_k=3)
                    if context_list:
                        rag_context = "\n".join(context_list)
                except Exception as e:
                    logger.warning(f"RAG query failed: {e}")

            architect = Agent(
                role="世界架构师 (World Architect)",
                goal="构建逻辑自洽、细节丰富的世界观",
                backstory=(
                    "你是一位富有想象力的世界架构师。你擅长为戏剧构建沉浸式的背景设定。"
                    "你明白'环境'如何影响'角色'，你会设定物理规则、社会常识以及当前的氛围，"
                    "确保所有演员都在同一个频道上表演。"
                ),
                llm=self.llm,
                verbose=True
            )

            task_desc = (
                f"请为以下剧本构建世界观。\n\n"
                f"【剧本主题】: {topic}\n"
                f"【舞台形式】: {stage}\n"
                f"【剧本大纲】:\n{scenario_text}\n"
            )
            
            if rag_context:
                task_desc += f"\n【参考资料(RAG)】:\n{rag_context}\n"

            task_desc += (
                f"\n任务要求:\n"
                f"1. 拟定一个【群名/房间名】 (group_name)。要符合舞台形式 (e.g., 微信群名 vs 法庭名)。\n"
                f"2. 撰写【世界观手册】 (world_bible)。包含地点、氛围、感官细节、必须遵守的规则。\n"
                f"3. 确保所有设定与剧本大纲一致。\n"
            )

            task = Task(
                description=task_desc,
                expected_output="A JSON object with group_name and world_bible.",
                agent=architect,
                output_pydantic=WorldBibleOutput
            )

            crew = Crew(
                agents=[architect],
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
                    data = WorldBibleOutput(**result.json_dict)
                except Exception:
                    pass

            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, WorldBibleOutput)
            
            if data:
                return data.model_dump()

            # Fallback
            return {
                "group_name": f"{topic} Stage",
                "world_bible": f"Setting for {topic} in {stage}."
            }

        except Exception as e:
            logger.error(f"Crew WorldBuilder Error: {e}")
            return {
                "group_name": f"{topic} Group",
                "world_bible": f"A story about {topic}."
            }
