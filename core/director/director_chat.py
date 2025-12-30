import json
from typing import List, Dict, Any
from openai import OpenAI
from core.utils.json_utils import extract_json

class DirectorChat:
    """
    Logic for interactive director consultation and script patching.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self._client = client
        self._modelName = model_name

    def consult(self, history: List[Dict], current_script_list: List[Dict]) -> Dict[str, Any]:
        script_ctx = json.dumps(current_script_list[:10], ensure_ascii=False) # Context limit
        
        system_prompt = f"""
        你现在是【AI 导演】。你的职责是协助用户（上帝）编排和调整正在进行的剧本。
        
        【当前剧本上下文】
        {script_ctx}
        
        【任务】
        1. 以自然、专业且富有创意的语气回复用户的咨询。
        2. 如果用户要求修改剧情走向、增加新事件或调整节奏，请提出具体的未来事件建议。
        3. **重要**：如果你决定更新剧本，请在回复的最末尾附带一个 JSON 代码块。
           格式要求：
           ```json
           {{ "type": "update_script", "new_events": [ 
               {{ "Time": "虚拟时间", "Event": "事件描述", "Goal": "阶段性目标" }},
               ... 
           ] }}
           ```
        4. 注意：只能修改“未来”的事件，不要试图修改已经发生的历史。
        """
        
        messages = [{"role": "system", "content": system_prompt}] + history
        
        try:
            response = self._client.chat.completions.create(
                model=self._modelName,
                messages=messages,
                temperature=0.7
            )
            content = response.choices[0].message.content
            action = extract_json(content) if "update_script" in content else None
            
            return {"reply": content, "action": action}
        except Exception as e:
            return {"reply": f"Director error: {e}", "action": None}
