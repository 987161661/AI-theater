import os
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, LLM
from openai import OpenAI

# Disable CrewAI Telemetry
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

logger = logging.getLogger("GodDirector")

class GodEventAction(BaseModel):
    """
    Structured output for God Mode intervention.
    """
    global_announcement: Optional[str] = Field(
        None, 
        description="A message to be broadcast to all actors and audience as a stage direction (e.g. 'Suddenly, a loud explosion is heard!')."
    )
    target_instructions: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Specific instructions for target actors. Key is actor name, Value is the instruction (e.g. 'You are stunned and cannot speak for a while.')."
    )
    memory_updates: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Specific memory injections for actors. Key is actor name, Value is the memory content (e.g. 'I saw a stone hit Bob.')."
    )
    state_updates: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Updates to actor states. Supported keys: 'stunned_actors' (list of names), 'silenced_actors' (list of names)."
    )

class GodDirector:
    """
    The intelligent agent behind God Mode.
    Interprets user intent and translates it into stage directions, actor instructions, and memory implants.
    """
    def __init__(self, client: OpenAI, model_name: str):
        self.model_name = model_name
        self.api_key = client.api_key
        self.base_url = str(client.base_url)
        
        llm_model = self.model_name
        if not llm_model.startswith("openai/"):
             llm_model = f"openai/{llm_model}"

        self.llm = LLM(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url
        )

    def process_intervention(self, 
                           user_input: str, 
                           target_actor: Optional[str], 
                           context: Dict[str, Any]) -> GodEventAction:
        """
        Process a user's sudden event injection.
        """
        
        # 1. Define Agent
        god_agent = Agent(
            role="神之手 (God Mode Operator)",
            goal="精准理解用户对剧情的干预意图，并将其转化为对演员的指令、记忆植入和舞台提示。",
            backstory=(
                "你是全知全能的剧场主宰。用户会直接给你一条指令（可能是模糊的、口语化的），"
                "你需要根据当前舞台的上下文（谁在场、发生了什么），将这条指令完美地融入剧情。"
                "你可以制造突发事件、控制演员行为、植入虚假记忆，甚至改变物理法则。"
                "你的输出必须直接、有效，并考虑到对其他在场角色的连带影响。"
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

        # 2. Construct Context Description
        active_actors = context.get("active_actors", [])
        current_event = context.get("current_event", "Unknown")
        recent_history = context.get("recent_history", [])
        
        context_str = (
            f"【当前场景】: {current_event}\n"
            f"【在场演员】: {', '.join(active_actors)}\n"
            f"【最近对话】: {str(recent_history[-3:])}\n"
        )
        
        if target_actor:
            context_str += f"【目标对象】: {target_actor} (用户指定了这个事件主要针对该角色)\n"

        # 3. Define Task
        task = Task(
            description=(
                f"用户发出了一个干预指令：\"{user_input}\"\n\n"
                f"背景信息：\n{context_str}\n\n"
                f"任务要求：\n"
                f"1. **解析意图**：用户想发生什么？是单纯的环境变化，还是针对某个角色的动作？\n"
                f"2. **生成舞台提示 (Global Announcement)**：如果这是所有人都能看到的（如打雷、有人倒地），生成一条简短有力的旁白。\n"
                f"3. **生成角色指令 (Target Instructions)**：如果目标角色受影响（如被打晕、被禁言、收到秘密纸条），给该角色具体的行动指南。\n"
                f"4. **生成记忆植入 (Memory Updates)**：\n"
                f"   - 受害者需要知道自己经历了什么（如'我感觉后脑勺一痛，然后失去了意识'）。\n"
                f"   - 旁观者（在场其他演员）如果能看到，也需要植入记忆（如'我看到一块石头飞向了{target_actor}'）。\n"
                f"5. **逻辑连贯性**：确保你的指令与上下文不冲突。如果用户说'被石头砸晕'，那么受害者应该被标记为晕倒（在指令中体现），旁观者应该表现出惊讶。\n"
            ),
            expected_output="一个结构化的 GodEventAction 对象，包含舞台提示、角色指令和记忆更新。",
            agent=god_agent,
            output_pydantic=GodEventAction
        )

        # 4. Execute
        crew = Crew(
            agents=[god_agent],
            tasks=[task],
            verbose=True
        )

        try:
            result = crew.kickoff()
            
            if hasattr(result, "pydantic") and result.pydantic:
                return result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                return GodEventAction(**result.json_dict)
            else:
                # Fallback
                return GodEventAction(global_announcement=f"⚡ {user_input}")

        except Exception as e:
            logger.error(f"God Mode Execution Error: {e}")
            # Fallback to simple broadcast
            return GodEventAction(global_announcement=f"⚡ {user_input}")
