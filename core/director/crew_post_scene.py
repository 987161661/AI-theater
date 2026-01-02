from crewai import Agent, Task, Crew, LLM
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from openai import OpenAI
import logging

logger = logging.getLogger("CrewPostScene")

class FactUpdate(BaseModel):
    new_facts: List[str] = Field(description="List of new objective facts established in this scene (e.g. 'The bomb was defused', 'John died')")
    resolved_mysteries: List[str] = Field(description="List of mysteries or questions answered")

class RelationshipUpdate(BaseModel):
    subject: str = Field(description="Name of the character")
    target: str = Field(description="Name of the target character")
    change: str = Field(description="Description of relationship change (e.g. 'Trusted -> Betrayed')")
    reason: str = Field(description="Why this change happened")

class SceneSummary(BaseModel):
    summary: str = Field(description="Concise summary of what happened")
    fact_updates: FactUpdate = Field(description="Facts to update in the world knowledge")
    relationship_updates: List[RelationshipUpdate] = Field(description="Changes in character relationships")
    next_scene_suggestions: List[str] = Field(description="Ideas for the next scene based on this outcome")

class CrewPostSceneAnalyst:
    """
    Analyzes the chat history of a finished scene to extract facts, relationship changes, and summary.
    """
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

    def analyze(self, chat_history: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the analysis crew on the chat history.
        """
        try:
            # Preprocess history to string
            history_text = ""
            for msg in chat_history:
                role = msg.get("role", "unknown")
                name = msg.get("name", role)
                content = msg.get("content", "")
                action = msg.get("action", "")
                if action:
                    history_text += f"{name}: {content} (Action: {action})\n"
                else:
                    history_text += f"{name}: {content}\n"
            
            theme = context.get("theme", "General")
            current_event = context.get("current_event", "Unknown Event")

            # 1. Fact Recorder
            fact_recorder = Agent(
                role="剧场书记官 (Theater Recorder)",
                goal="从对话中提取客观事实和世界观变动",
                backstory="你负责记录演出中发生的不可逆转的事实。你只关心发生了什么（Who did What），不关心感受。",
                llm=self.llm,
                verbose=True
            )

            # 2. Relationship Psychologist
            psychologist = Agent(
                role="情感分析师 (Relationship Psychologist)",
                goal="分析人物关系和情感态度的变化",
                backstory="你关注角色之间的微妙互动。谁背叛了谁？谁爱上了谁？你需要敏锐地捕捉这些变化。",
                llm=self.llm,
                verbose=True
            )

            # 3. Narrative Lead
            narrative_lead = Agent(
                role="叙事主管 (Narrative Lead)",
                goal="总结剧情并规划未来",
                backstory="你负责将这一幕的混乱收束为一个清晰的总结，并为下一幕提供灵感。",
                llm=self.llm,
                verbose=True
            )

            # Tasks
            task_facts = Task(
                description=(
                    f"分析以下场景对话，提取新的客观事实。\n"
                    f"【场景主题】: {current_event}\n"
                    f"【对话记录】:\n{history_text}\n"
                ),
                expected_output="JSON with new_facts and resolved_mysteries.",
                agent=fact_recorder,
                output_pydantic=FactUpdate
            )

            task_relationships = Task(
                description=(
                    f"分析角色之间的关系变化。\n"
                    f"【对话记录】:\n{history_text}\n"
                ),
                expected_output="JSON list of relationship updates.",
                agent=psychologist,
                output_pydantic=RelationshipUpdate # Note: CrewAI task output_pydantic expects a single model usually, but list might work if wrapped or we use a wrapper model.
                # Let's use a wrapper model for safety in next step or just text parsing if complex list.
                # Actually, let's define a wrapper for list in Pydantic.
            )
            
            # Re-defining wrapper for task output safety
            class RelationshipList(BaseModel):
                updates: List[RelationshipUpdate]

            task_relationships.output_pydantic = RelationshipList

            task_summary = Task(
                description=(
                    f"综合事实和情感变化，生成本幕总结和后续建议。\n"
                    f"必须整合前两个任务的发现。"
                ),
                expected_output="JSON with summary, fact_updates, relationship_updates, and next_scene_suggestions.",
                agent=narrative_lead,
                context=[task_facts, task_relationships],
                output_pydantic=SceneSummary
            )

            crew = Crew(
                agents=[fact_recorder, psychologist, narrative_lead],
                tasks=[task_facts, task_relationships, task_summary],
                verbose=True
            )

            result = crew.kickoff()
            
            # Extract data
            data = None
            if hasattr(result, "pydantic") and result.pydantic:
                data = result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                try:
                    data = SceneSummary(**result.json_dict)
                except Exception:
                    pass

            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, SceneSummary)
            
            if data:
                return data.model_dump()

            # Fallback
            return {
                "summary": "Scene finished.",
                "fact_updates": {"new_facts": [], "resolved_mysteries": []},
                "relationship_updates": [],
                "next_scene_suggestions": []
            }

        except Exception as e:
            logger.error(f"Crew PostScene Error: {e}")
            return {
                "summary": f"Analysis failed: {str(e)}",
                "fact_updates": {"new_facts": [], "resolved_mysteries": []},
                "relationship_updates": [],
                "next_scene_suggestions": []
            }
