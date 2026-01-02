from crewai import Agent, Task, Crew, LLM
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import json
from openai import OpenAI
import logging

logger = logging.getLogger("CrewCritic")

# Pydantic models for structured output
class CritiquePoint(BaseModel):
    issue: str = Field(description="Description of the issue found")
    severity: str = Field(description="Severity: 'Critical', 'Major', 'Minor'")
    suggestion: str = Field(description="How to fix it")

class LogicReview(BaseModel):
    flaws: List[CritiquePoint] = Field(description="List of logical flaws")
    consistency_score: int = Field(description="Score from 1-10")

class DramaReview(BaseModel):
    tension_issues: List[CritiquePoint] = Field(description="Issues with dramatic tension or pacing")
    character_issues: List[CritiquePoint] = Field(description="Issues with character motivation or voice")
    entertainment_score: int = Field(description="Score from 1-10")

class FinalVerdict(BaseModel):
    total_score: int = Field(description="Overall score 1-10")
    is_pass: bool = Field(description="Whether the script is ready for production")
    summary: str = Field(description="Executive summary of the review")
    key_improvements: List[str] = Field(description="Top 3 suggestions for improvement")

class CrewCritic:
    """
    Multi-agent system for in-depth script evaluation.
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

    def review(self, script_data: Dict[str, Any], topic: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the critic crew to evaluate the script.
        """
        try:
            genre = constraints.get("genre", "General")
            stage = constraints.get("stage", "General Stage")
            script_str = json.dumps(script_data, indent=2, ensure_ascii=False)

            # 1. Logic Analyst
            logic_analyst = Agent(
                role="逻辑分析师 (Logic Analyst)",
                goal="找出剧本中的逻辑硬伤和因果断裂",
                backstory="你是一个冷酷无情的逻辑机器。你不在乎文笔，只在乎事情发生得是否合理，时间线是否冲突。",
                llm=self.llm,
                verbose=True
            )

            # 2. Drama Critic
            drama_critic = Agent(
                role="戏剧评论家 (Drama Critic)",
                goal="评估剧本的张力、节奏和娱乐性",
                backstory="你是百老汇资深评论家。你关注的是观众会不会睡着，角色是否有灵魂，冲突是否足够激烈。",
                llm=self.llm,
                verbose=True
            )

            # 3. Chief Editor (Aggregator)
            chief_editor = Agent(
                role="主编 (Chief Editor)",
                goal="综合各方意见，给出最终评审结果",
                backstory="你是剧本部门的负责人。你需要听取逻辑分析师和戏剧评论家的意见，决定这个剧本是退回重写还是通过。",
                llm=self.llm,
                verbose=True
            )

            # Tasks
            task_logic = Task(
                description=(
                    f"请审查以下剧本的逻辑性。\n"
                    f"【剧本】: \n{script_str}\n\n"
                    f"重点检查：\n1. 时间线是否混乱？\n2. 事件因果是否成立？\n3. 角色行为是否违背物理常识？"
                ),
                expected_output="JSON with flaws list and consistency_score.",
                agent=logic_analyst,
                output_pydantic=LogicReview
            )

            task_drama = Task(
                description=(
                    f"请审查以下剧本的艺术性。\n"
                    f"【主题】: {topic}\n"
                    f"【流派】: {genre}\n"
                    f"【舞台】: {stage}\n"
                    f"【剧本】: \n{script_str}\n\n"
                    f"重点检查：\n1. 冲突是否足够？\n2. 节奏是否拖沓？\n3. 角色动机是否清晰？"
                ),
                expected_output="JSON with tension_issues, character_issues, and entertainment_score.",
                agent=drama_critic,
                output_pydantic=DramaReview
            )

            task_verdict = Task(
                description=(
                    f"综合逻辑分析师和戏剧评论家的报告，给出最终结论。\n"
                    f"如果总分低于 6 分，必须标记为 is_pass=False。\n"
                    f"给出 3 条最重要的修改建议。"
                ),
                expected_output="JSON with total_score, is_pass, summary, and key_improvements.",
                agent=chief_editor,
                context=[task_logic, task_drama],
                output_pydantic=FinalVerdict
            )

            crew = Crew(
                agents=[logic_analyst, drama_critic, chief_editor],
                tasks=[task_logic, task_drama, task_verdict],
                verbose=True
            )

            result = crew.kickoff()
            
            data = result.pydantic
            if not data and hasattr(result, "raw"):
                from core.utils.json_parser import JSONParser
                data = JSONParser.parse(result.raw, FinalVerdict)
            
            if data:
                return data.model_dump()
            
            # Fallback
            return {
                "total_score": 5,
                "is_pass": False,
                "summary": "Review failed to generate structured output.",
                "key_improvements": ["Retry review"]
            }

        except Exception as e:
            logger.error(f"Crew Critic Error: {e}")
            return {
                "total_score": 0,
                "is_pass": False,
                "summary": f"Error: {str(e)}",
                "key_improvements": []
            }
