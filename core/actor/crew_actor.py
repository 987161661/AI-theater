from crewai import Agent, Task, Crew, LLM
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from openai import OpenAI
import logging

logger = logging.getLogger("CrewActor")

class ActorAction(BaseModel):
    thought: str = Field(description="Internal thought process regarding the situation", default="")
    willingness: int = Field(description="Willingness to speak (0-10)", default=5)
    content: str = Field(description="The dialogue spoken by the actor. Use '[PASS]' if staying silent.", default="")
    action: str = Field(description="The physical action or facial expression accompanying the dialogue", default="")
    is_finished: bool = Field(description="Whether the actor believes the current scene/conversation should end", default=False)

class CrewActor:
    def __init__(self, name: str, system_prompt: str, llm_config: Dict[str, Any]):
        self.name = name
        self.system_prompt = system_prompt
        
        # Extract LLM config
        # Assuming llm_config contains 'model', 'api_key', 'base_url'
        self.model_name = llm_config.get("model", "gpt-4")
        self.api_key = llm_config.get("api_key", "")
        self.base_url = llm_config.get("base_url", "https://api.openai.com/v1")
        
        logger.info(f"Initializing CrewActor {name} with model: {self.model_name}, base_url: {self.base_url}")

        # Initialize CrewAI LLM
        llm_model = self.model_name
        
        # Ensure we have a string
        if not llm_model:
            llm_model = "gpt-4"
            
        # Fix for LiteLLM: It needs a provider prefix for custom base_urls often, 
        # or if the model name is ambiguous.
        # If a base_url is provided, we assume it's an OpenAI-compatible endpoint.
        # Even if the model name contains '/', we should prepend 'openai/' so LiteLLM knows which client to use.
        if self.base_url and not llm_model.startswith("openai/"):
            llm_model = f"openai/{llm_model}"
             
        logger.info(f"Final LLM Model string for {name}: {llm_model}")

        self.llm = LLM(
            model=llm_model,
            api_key=self.api_key if self.api_key else "NA", # LiteLLM sometimes needs a non-empty key
            base_url=self.base_url
        )
        
        # Create the Agent once (persistent identity)
        self.agent = Agent(
            role=self.name,
            goal=f"Portray the character {self.name} authentically in the AI Theater.",
            backstory=self.system_prompt,
            verbose=True, # Set to True for debugging
            allow_delegation=False,
            llm=self.llm
        )

    def perform(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a performance turn using CrewAI.
        
        Context expects:
        - event: str (Scene name)
        - description: str (Scene description)
        - goal: str (Scene goal)
        - memories: List[str] or str
        - chat_history: List[Dict]
        - stage_directives: str
        - blackboard_facts: str (Global facts)
        """
        
        event = context.get("event", "Unknown Scene")
        desc = context.get("description", "")
        goal = context.get("goal", "")
        memories = context.get("memories", "")
        history = context.get("chat_history", [])
        directives = context.get("stage_directives", "")
        blackboard_facts = context.get("blackboard_facts", "No global facts known.")
        
        # Format chat history for the prompt
        formatted_history_lines = []
        for msg in history:
            line = f"{msg['name']}: {msg.get('content', '')}"
            action = msg.get('action', '')
            if action:
                line += f" [Action: {action}]"
            formatted_history_lines.append(line)
        formatted_history = "\n".join(formatted_history_lines)
        
        # Collect own recent lines for negative constraints
        my_recent_lines = []
        for msg in reversed(history):
            if msg.get('name') == self.name:
                content = msg.get('content', '').strip()
                if content and content not in ["[PASS]", ""]:
                    my_recent_lines.append(content)
                if len(my_recent_lines) >= 3: # Check last 3 unique lines
                    break
        
        negative_constraints = ""
        if my_recent_lines:
            forbidden_phrases = "\n".join([f"- {line}" for line in my_recent_lines])
            negative_constraints = (
                f"\n**NEGATIVE CONSTRAINTS (DO NOT REPEAT)**:\n"
                f"You have recently said the following lines. DO NOT repeat them or say anything semantically identical:\n"
                f"{forbidden_phrases}\n"
                f"Be creative and move the conversation forward.\n"
            )
        
        task_description = (
            f"**Current Scene**: {event}\n"
            f"**Environment**: {desc}\n"
            f"**Goal**: {goal}\n\n"
            f"**Global Context (Blackboard)**:\n{blackboard_facts}\n\n"
            f"**Your Memories**:\n{memories}\n\n"
            f"**Recent Dialogue History**:\n{formatted_history}\n\n"
            f"**Stage Directions**:\n{directives}\n\n"
            f"{negative_constraints}"
            f"Based on your character and the context above, respond with your next line and action. "
            f"**Willingness Logic**: "
            f"- If your Goal ('{goal}') is achieved, your Willingness should DROP significantly."
            f"- If the conversation is cooling down or you have nothing new to add, set Willingness low (<3) and content to '[PASS]'."
            f"- Only speak if you have a strong motivation or need to react."
        )

        task = Task(
            description=task_description,
            expected_output="A VALID JSON object matching the ActorAction schema. NO markdown, NO thoughts outside JSON. Just the raw JSON.",
            agent=self.agent,
            output_json=ActorAction
        )

        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )

        try:
            result = crew.kickoff()
            
            # Safe extraction
            if hasattr(result, "pydantic") and result.pydantic:
                return result.pydantic.model_dump()
            elif hasattr(result, "json_dict") and result.json_dict:
                return result.json_dict
            else:
                # Fallback parsing if string returned (shouldn't happen with output_json)
                error_msg = f"Error: Model failed to output JSON. Raw: {str(result)[:200]}"
                logger.error(f"CrewActor {self.name} failed to return JSON. Raw: {result}")
                return {"content": "[PASS]", "action": "", "is_finished": False, "willingness": 0, "thought": error_msg}

        except Exception as e:
            logger.error(f"Error during CrewActor performance: {e}")
            # Fallback: Stay silent if error occurs
            return {"content": "[PASS]", "action": "stays silent (error)", "is_finished": False, "willingness": 0, "thought": f"Error: {str(e)}"}
