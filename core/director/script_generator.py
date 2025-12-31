import pandas as pd
import json
import re
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI

from core.utils.json_parser import JSONParser, ScriptModel
from core.director.critic_agent import CriticAgent

logger = logging.getLogger("ScriptGenerator")

class ScriptGenerator:
    """
    Logic for generating scripts with specific thematic constraints.
    Supports structured JSON templates with Time, Event, and Goal.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name
        self._critic = CriticAgent(client, model_name)

    def generate(self, topic: str, constraints: Dict[str, Any]) -> pd.DataFrame:
        """
        Generates a structured script using a Writer-Critic loop.
        """
        max_retries = 2
        current_attempt = 0
        feedback = ""

        while current_attempt <= max_retries:
            prompt = self._build_prompt(topic, constraints, feedback)
            response = self._query(prompt)
            sc_data = JSONParser.parse(response, ScriptModel)
            
            if not sc_data:
                current_attempt += 1
                continue

            # Phase 2: Review by Critic
            review_result = self._critic.review(sc_data.model_dump(), topic, constraints)
            is_pass = review_result.get("is_pass", False)
            score = review_result.get("score", 0)
            
            logger.info(f"Script Attempt {current_attempt + 1}: Score {score}, Pass: {is_pass}")

            if is_pass or current_attempt == max_retries:
                return self._to_dataframe(sc_data)
            
            # Prepare feedback for the next round
            feedback = (
                f"【上轮评审意见 (得分: {score})】\n"
                f"- 逻辑漏洞: {', '.join(review_result.get('logic_flaws', []))}\n"
                f"- 改进建议: {', '.join(review_result.get('tension_suggestions', []))}\n"
                "请根据以上意见修正并产生更好的剧本。"
            )
            current_attempt += 1

        return pd.DataFrame()

    def _build_prompt(self, topic: str, constraints: Dict[str, Any], feedback: str = "") -> str:
        genre = constraints.get("genre", "随机")
        reality = constraints.get("reality", "艺术现实")
        min_events = constraints.get("min_events", 3)
        max_events = constraints.get("max_events", 6)
        stage = constraints.get("stage", "聊天群聊")

        prompt = (
            f"请构思一个极具创意的剧本。\n"
            f"【主题】: {topic}\n"
            f"【流派】: {genre}\n"
            f"【世界观现实度】: {reality}\n"
            f"【舞台设定】: 本剧本发生在一个【{stage}】中。\n"
        )
        
        if feedback:
            prompt += f"\n{feedback}\n"

        prompt += (
            "\n请务必输出标准的 JSON 格式，包含以下字段：\n"
            "1. 'theme': 剧本主题（一句话）。\n"
            f"2. 'events': 一个包含 {min_events} 到 {max_events} 个关键事件的列表，每个事件包含 'Time' (虚拟时间), 'Event' (事件描述), 'Goal' (收敛/阶段性目标)。\n\n"
            "示例格式：\n"
            "```json\n"
            "{\n"
            "  \"theme\": \"深海潜艇中的密室逃脱\",\n"
            "  \"events\": [\n"
                "    {\"Time\": \"Day 1 08:00\", \"Event\": \"潜艇突然失去动力，警报响起。\", \"Goal\": \"查明故障原因\"},\n"
                "    {\"Time\": \"Day 1 09:30\", \"Event\": \"发现通讯设备被蓄意破坏。\", \"Goal\": \"找出破坏者\"}\n"
            "  ]\n"
            "}\n"
            "```\n"
            "请直接输出 JSON，不要包含多余解释。"
        )
        return prompt

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

    def generate_theme(self, genre: str, reality: str) -> str:
        """
        Generates a creative one-sentence script theme based on genre and reality.
        """
        prompt = (
            f"请作为一个金牌编剧，根据以下设定，构思一个极具创意和张力的【剧本主题】（一句话）。\n"
            f"【流派】: {genre}\n"
            f"【世界观现实度】: {reality}\n\n"
            "要求：\n"
            "1. 只输出一句话，包含核心冲突。不要包含任何解释或开场白。\n"
            "2. 语言要凝练、抓人、有画面感。\n"
            "3. 主题要具体（例如：‘深海潜艇中的密室逃脱’ 而不是 ‘海底的冒险’）。"
        )
        response = self._query(prompt)
        # Simple cleanup to remove quotes if LLM adds them
        theme = response.strip().replace('"', '').replace('“', '').replace('”', '')
        return theme


    def _query(self, prompt: str) -> str:
        """Helper to call LLM."""
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        return response.choices[0].message.content
    
    def adapt_script(self, history_summary: str, current_plan: Dict[str, str], theme: str, available_cast: List[str] = None) -> Dict[str, str]:
        """
        Adapts the next event based on the history of what actually happened.
        STRICTLY enforces consistency: No new characters, no setting changes.
        """
        cast_str = ", ".join(available_cast) if available_cast else "Unknown"
        
        prompt = (
            f"你需要作为一个【AI导演】，根据刚刚发生的剧情，动态调整接下来的剧本。\n"
            f"【剧本主题】: {theme}\n"
            f"【可用演员班底 (严禁新增/修改)】: {cast_str}\n"
            f"【刚刚发生的剧情总结】: {history_summary}\n"
            f"【原定接下来的剧情】: {current_plan}\n\n"
            f"🔴 **核心约束 (必须遵守)**：\n"
            f"1. **人物一致性**：绝对禁止引入新角色！绝对禁止修改现有角色的核心设定！必须使用【可用演员班底】中的人物。\n"
            f"2. **人物弧光**：关注人物的内心变化和性格发展。根据上一幕的冲突，让人物自然地走向下一幕。\n"
            f"3. **场景一致性**：严禁随意切换大的世界观或物理规则。\n"
            f"4. **收敛性**：剧情必须向前推进，不能原地打转。\n\n"
            f"任务：\n"
            f"1. 分析‘刚刚发生的剧情’，判断是否需要调整下一幕。\n"
            f"2. 细化或修改【原定剧情】，使其符合人物当下的心理状态。\n"
            f"3. 输出修改后的 Time, Event, Goal。\n\n"
            f"输出格式(JSON):\n"
            f"```json\n"
            f"{{\n"
            f"  \"Time\": \"Day X HH:MM\",\n"
            f"  \"Event\": \"一句话描述事件 (需包含 {cast_str} 中的角色)\",\n"
            f"  \"Goal\": \"具体的收敛目标 (指导演员如何行动)\"\n"
            f"}}\n"
            f"```"
        )
        
        response = self._query(prompt)
        
        # Simple extraction
        from core.utils.json_parser import JSONParser
        from pydantic import BaseModel
        
        class SingleEvent(BaseModel):
            Time: str
            Event: str
            Goal: str
        
        event_data = JSONParser.parse(response, SingleEvent)
        if event_data:
            return event_data.model_dump()
        
        # Fallback if parsing fails - return original plan
        return current_plan
