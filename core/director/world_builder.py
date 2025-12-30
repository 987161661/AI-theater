import json
import re
import logging
from typing import Dict, Any, Optional
import pandas as pd
from openai import OpenAI

from core.utils.json_parser import JSONParser, WorldBibleModel

logger = logging.getLogger("WorldBuilder")

class WorldBuilder:
    """
    Logic for building the "World Bible" or global context for the scenario.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    def build(self, topic: str, script_df: pd.DataFrame, stage: str) -> Dict[str, str]:
        """
        Builds a unified world context based on the script and topic.
        Returns {group_name, world_bible}.
        """
        scenario_text = script_df.to_markdown(index=False)
        
        prompt = (
            f"你现在是【总导演】。请为剧本主题【{topic}】完成以下两项任务：\n\n"
            f"任务一：【拟定群名/房间名】\n"
            f"请根据剧本主题和舞台设定【{stage}】的特点，取一个恰到好处的名字。\n"
            f"要求：简短有力，符合语境。\n\n"
            f"任务二：【统一世界观设定】\n"
            f"生成一段“绝对事实”分发给所有演员，防止认知冲突。\n"
            f"要求：明确地点、氛围、感官细节及所有人都必须遵守的物理/社会规则。字数 200 字以内。\n\n"
            f"【参考剧本时间线】\n{scenario_text}\n\n"
            f"请务必输出 JSON 格式，包含以下字段：\n"
            f"- `group_name`: 拟定的群名。\n"
            f"- `world_bible`: 世界观设定文本。\n"
            "直接输出 JSON，不要包含多余解释。"
        )

        try:
            response = self._query(prompt)
            data = JSONParser.parse(response, WorldBibleModel)
            if data:
                return data.model_dump()
            
            return {
                "group_name": f"{topic}讨论组",
                "world_bible": response
            }
        except Exception as e:
            logger.error(f"Error building world bible: {e}")
            return {"group_name": topic, "world_bible": "Error generating context."}

    def _query(self, prompt: str) -> str:
        """Helper to call LLM."""
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
