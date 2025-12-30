import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from core.utils.json_parser import JSONParser, ScriptModel

logger = logging.getLogger("CriticAgent")

class CriticAgent:
    """
    Evaluates scripts and provides constructive feedback to the ScriptGenerator.
    Focuses on logic, tension, character motivation, and stage appropriateness.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    def review(self, script_data: Dict[str, Any], topic: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reviews a draft script and returns quality scores and suggestions.
        """
        genre = constraints.get("genre", "随机")
        stage = constraints.get("stage", "默认舞台")
        
        prompt = (
            f"你现在是【资深剧评人】和【舞台监督】。\n"
            f"请从专业角度审视以下剧本草稿，并给出改进意见。\n\n"
            f"【原始主题】: {topic}\n"
            f"【预期流派】: {genre}\n"
            f"【舞台设定】: {stage}\n\n"
            f"【剧本草稿】:\n{json.dumps(script_data, indent=2, ensure_ascii=False)}\n\n"
            "评价维度：\n"
            "1. 逻辑自洽性：事件之间是否有因果关系？是否有硬伤？\n"
            "2. 戏剧张力：情节是否平淡？冲突是否足够激烈？\n"
            "3. 角色动机：预设的每个阶段性目标是否合理？\n"
            "4. 舞台适配：是否符合当前舞台（如群聊、法庭）的交互逻辑？\n\n"
            "任务：输出 JSON，包含：\n"
            "- 'score': 总体评分 (1-10)\n"
            "- 'logic_flaws': 逻辑漏洞描述 (列表)\n"
            "- 'tension_suggestions': 提升张力的具体建议 (列表)\n"
            "- 'is_pass': 是否达到发布标准 (true/false)\n"
            "直接输出 JSON，不要多余解释。"
        )

        try:
            response = self._query(prompt)
            # Use a simple dict parse here as the schema is small/ad-hoc
            data = JSONParser.parse(response, dict)
            return data if data else {"score": 5, "is_pass": False, "logic_flaws": ["解析失败"]}
        except Exception as e:
            logger.error(f"Critic review error: {e}")
            return {"score": 0, "is_pass": False, "logic_flaws": [str(e)]}

    def _query(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4 # Lower temperature for stable evaluation
        )
        return response.choices[0].message.content
