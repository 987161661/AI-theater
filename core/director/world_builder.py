import json
import re
import logging
from typing import Dict, Any, Optional
import pandas as pd
from openai import OpenAI
import streamlit as st

from core.utils.json_parser import JSONParser, WorldBibleModel

logger = logging.getLogger("WorldBuilder")

class WorldBuilder:
    """
    Logic for building the "World Bible" or global context for the scenario.
    """
    def __init__(self, client: OpenAI, model_name: str, rag_engine: Any = None):
        self._client = client
        self._modelName = model_name
        self.rag_engine = rag_engine

    def build(self, topic: str, script_df: pd.DataFrame, stage: str) -> Dict[str, str]:
        """
        Builds a unified world context based on the script and topic.
        Returns {group_name, world_bible}.
        """
        try:
            # Safe markdown conversion with fallback
            try:
                scenario_text = script_df.to_markdown(index=False)
            except Exception as e:
                logger.warning(f"Markdown conversion failed: {e}, using CSV format")
                scenario_text = script_df.to_csv(index=False)
            
            prompt = (
                "你现在是【总导演】。请为剧本主题【" + topic + "】完成以下两项任务:\n\n"
                "任务一:【拟定群名/房间名】\n"
                "请根据剧本主题和舞台设定【" + stage + "】的特点,取一个恰到好处的名字。\n"
                "要求:简短有力,符合语境。\n\n"
                "任务二:【统一世界观设定】\n"
                "生成一段绝对事实分发给所有演员,防止认知冲突。\n"
                "要求:明确地点、氛围、感官细节及所有人都必须遵守的物理/社会规则。字数 200 字以内。\n\n"
                "【参考剧本时间线】\n" + scenario_text + "\n\n"
            )
            
            # Add RAG Context if available
            if self.rag_engine:
                try:
                    context = self.rag_engine.query(topic, top_k=3)
                    if context:
                        prompt += "\n【参考背景素材 (RAG)】\n" + "\n---\n".join(context) + "\n"
                except Exception as e:
                    logger.warning(f"RAG query failed: {e}")

            prompt += (
                "请务必输出 JSON 格式,包含以下字段:\n"
                "- `group_name`: 拟定的群名。\n"
                "- `world_bible`: 世界观设定文本。\n"
                "直接输出 JSON,不要包含多余解释。"
            )

            response = self._query(prompt)
            
            # Try to parse as structured JSON first
            data = JSONParser.parse(response, WorldBibleModel)
            if data:
                return data.model_dump()
            
            # Fallback: try manual JSON extraction
            try:
                # Look for JSON in response
                json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if 'group_name' in parsed and 'world_bible' in parsed:
                        return parsed
            except:
                pass
            
            # Final fallback: use response as world_bible
            return {
                "group_name": topic + "剧场",
                "world_bible": response[:500] if len(response) > 500 else response
            }
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ WorldBuilder Error: {error_msg}")
            logger.error(f"Error building world bible: {error_msg}")
            
            # Provide a reasonable fallback even on error
            return {
                "group_name": topic + "讨论组",
                "world_bible": "一个关于【" + topic + "】的" + stage + "场景,所有参与者将在这里展开互动。"
            }

    def _query(self, prompt: str) -> str:
        """Helper to call LLM."""
        response = self._client.chat.completions.create(
            model=self._modelName,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
