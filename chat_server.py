import asyncio
import logging
import os
import re  # Moved to top level

# Disable CrewAI Telemetry
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from core.llm_provider import LLMProvider
from core.state.db_manager import DBManager
from core.state.performance_blackboard import PerformanceBlackboard
from core.actor.memory_bank import MemoryBank
from core.stage.stage_rules import StageRules
from core.utils.prompt_templates import get_stage_directives, get_willingness_protocol
from core.director.crew_script_generator import CrewScriptGenerator as ScriptGenerator
from core.director.crew_post_scene import CrewPostSceneAnalyst
from core.director.god_director import GodDirector, GodEventAction
from core.actor.crew_actor import CrewActor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StageServer")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()}
    )

# --- Models ---
class ActorConfig(BaseModel):
    name: str
    llm_config: Dict[str, Any]
    system_prompt: str
    memory: str = ""

class ScriptEvent(BaseModel):
    timeline: str
    event: str
    characters: Optional[str] = "所有人"
    description: Optional[str] = ""
    location: Optional[str] = "默认地点"
    goal: str = ""
    max_turns: int = 30  # Increased to allow Cold Field to be the primary terminator

class InitRequest(BaseModel):
    script: List[ScriptEvent]          # List of script events
    actors: List[ActorConfig]          # List of actor configurations
    world_bible: Optional[Dict[str, str]] = {}
    stage_type: Optional[str] = "聊天群聊"

class GenerateThemeRequest(BaseModel):
    genre: str
    reality: str
    stage: str = "聊天群聊"
    count: int = 1
    llm_config: Dict[str, Any]

@app.post("/generate_theme")
async def generate_theme(request: GenerateThemeRequest):
    try:
        logger.info(f"Received Theme Generation Request. Genre: {request.genre}, Stage: {request.stage}, Count: {request.count}")
        # Reconstruct LLM Client
        llm_provider = LLMProvider(
            api_key=request.llm_config.get("api_key"),
            base_url=request.llm_config.get("base_url"),
            model_name=request.llm_config.get("model")
        )
        
        # Instantiate Generator
        generator = ScriptGenerator(llm_provider.client, llm_provider.model_name)
        
        # Generate in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        themes = await loop.run_in_executor(
            None,
            lambda: generator.generate_themes(request.genre, request.reality, request.stage, request.count)
        )
        
        return {"themes": themes}
    except Exception as e:
        logger.error(f"Theme generation failed: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

# --- State Management (God Mode Enabled) ---
class StageManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.script: List[ScriptEvent] = []
        self.actors: Dict[str, ActorConfig] = {}
        self.llm_clients: Dict[str, LLMProvider] = {}
        self.crew_actors: Dict[str, CrewActor] = {}
        
        # State & Persistence
        self.db = DBManager()
        self.blackboard = PerformanceBlackboard()
        self.actor_memories: Dict[str, MemoryBank] = {}
        
        self.performance_id: Optional[int] = None
        self.is_playing = False
        self.current_index = 0
        self.world_bible = {}
        self.stage_type = "聊天群聊"
        
        self._loopTask = None
        self._eventQueue = asyncio.Queue()
        self.active_scene_chat_history: List[Dict[str, Any]] = []
        self.debug_mode = False
        self.is_fresh_start = False # Track if performance just started to preserve context

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, msg: Dict):
        for ws in self.active_connections:
            try:
                await ws.send_json(msg)
            except:
                pass

    def initialize(self, data: InitRequest):
        self.script = data.script
        self.actors = {a.name: a for a in data.actors}
        self.world_bible = data.world_bible
        self.stage_type = data.stage_type
        
        # Persist to DB
        script_id = self.db.save_script("Live Performance", [s.model_dump() for s in self.script])
        self.performance_id = self.db.create_performance(script_id, self.world_bible)
        
        for name, cfg in self.actors.items():
            m = cfg.llm_config
            self.llm_clients[name] = LLMProvider(m["api_key"], m["base_url"], m["model"])
            
            # Initialize CrewActor
            self.crew_actors[name] = CrewActor(name, cfg.system_prompt, m)
            
            # Setup structured MemoryBank
            initial_memories = [cfg.memory] if cfg.memory else []
            self.actor_memories[name] = MemoryBank(name, initial_memories)
            
            # Save actor state
            self.db.save_actor_state(self.performance_id, name, cfg.model_dump(), initial_memories)
            
        self.current_index = 0
        self.is_playing = False
        self.blackboard.clear()
        logger.info(f"Initialized performance {self.performance_id} with {len(self.script)} events.")

    async def broadcast_debug(self, message: str):
        """Broadcast a debug message if debug mode is on."""
        if self.debug_mode:
            await self.broadcast({
                "type": "debug_log",
                "content": message,
                "timestamp": __import__("time").strftime("%H:%M:%S")
            })

    async def start(self):
        if not self.script:
            logger.warning("Attempted to start with empty script!")
            await self.broadcast({"type": "system", "content": "⚠️ 舞台剧本为空！请尝试点击页面上方的【🚀 重新初始化舞台】按钮。"})
            return
            
        if not self.actors:
            logger.warning("Attempted to start with empty actors!")
            await self.broadcast({"type": "system", "content": "⚠️ 演员阵容为空！请尝试点击页面上方的【🚀 重新初始化舞台】按钮。"})
            return

        self.is_playing = True
        self.is_fresh_start = True
        if not self._loopTask or self._loopTask.done():
            self._loopTask = asyncio.create_task(self._main_loop())

    def pause(self):
        self.is_playing = False

    def jump(self, index: int):
        if 0 <= index < len(self.script):
            self.current_index = index
            logger.info(f"Jumped to event {index}")

    def _get_god_director(self):
        """Helper to get a GodDirector instance using the best available LLM."""
        # Priority: 'Director' -> GPT-4 -> Any
        client = self.llm_clients.get("Director")
        if not client:
            for c in self.llm_clients.values():
                if "gpt-4" in c.model_name.lower():
                    client = c
                    break
        if not client:
            client = next(iter(self.llm_clients.values()), None)
            
        if client:
            return GodDirector(client.client, client.model_name)
        return None

    async def _process_god_injection(self, content: str, target_actor: Optional[str] = None):
        """Internal handler for processing God Mode requests via CrewAI."""
        god_director = self._get_god_director()
        if not god_director:
            # Fallback: simple injection if no LLM
            await self._eventQueue.put({"content": content, "target": target_actor} if target_actor else content)
            return

        # Build Context
        # We need current scene info. 
        # Since this runs async, we grab a snapshot of current state.
        active_actors = list(self.actors.keys()) # Rough approx, or check active_actors logic
        # Ideally we want the active actors of the CURRENT event, but we can just pass all for now or check current script event
        current_event_data = "No active event"
        if 0 <= self.current_index < len(self.script):
             current_event_data = self.script[self.current_index].event
        
        context = {
            "active_actors": active_actors,
            "current_event": current_event_data,
            "recent_history": self.blackboard.get_recent_dialogue_struct(3)
        }

        # Run GodDirector in thread
        await self.broadcast({"type": "stage_direction", "content": "⚡ 上帝正在编织命运..."})
        loop = asyncio.get_event_loop()
        action = await loop.run_in_executor(
            None,
            lambda: god_director.process_intervention(content, target_actor, context)
        )
        
        # Put the structured action into the queue
        await self._eventQueue.put(action)

    async def inject_event(self, content: str):
        """God Mode: Inject a sudden event into the live session."""
        await self._process_god_injection(content, None)

    async def inject_targeted_event(self, actor_name: str, content: str):
        """God Mode: Inject a specific event for an actor."""
        await self._process_god_injection(content, actor_name)

    async def time_travel(self, new_time: str):
        """God Mode: Adjust the timeline."""
        # Update current event's timeline if possible, or just broadcast
        if 0 <= self.current_index < len(self.script):
            self.script[self.current_index].timeline = new_time
        
        msg = f"⏳ [时空穿梭] 时间已变更为: {new_time}"
        if self.performance_id:
            self.db.log_event(self.performance_id, "SYSTEM", "stage_direction", msg)
        await self.broadcast({"type": "stage_direction", "content": msg})

    async def _apply_god_action(self, action: GodEventAction):
        """Apply the structured God Mode action."""
        # 1. Global Announcement
        if action.global_announcement:
             msg = f"⚡ [神谕]: {action.global_announcement}"
             # Add to everyone's memory
             for mb in self.actor_memories.values():
                 mb.add(msg)
             if self.performance_id:
                 self.db.log_event(self.performance_id, "GOD", "stage_direction", msg)
             await self.broadcast({"type": "stage_direction", "content": msg})

        # 2. Target Instructions
        if action.target_instructions:
             for name, instr in action.target_instructions.items():
                 if name in self.actor_memories:
                     # High priority instruction
                     self.actor_memories[name].add(f"【神之指令 (立即执行)】: {instr}")
                     await self.broadcast_debug(f"⚡ Command -> {name}: {instr}")

        # 3. Memory Updates
        if action.memory_updates:
             for name, mem in action.memory_updates.items():
                 if name in self.actor_memories:
                     self.actor_memories[name].add(f"【植入记忆】: {mem}")
                     logger.info(f"Injected memory for {name}: {mem}")

    async def _main_loop(self):
        logger.info("Main Loop Started")
        await self.broadcast({"type": "system", "content": "🎬 表演正式开始！"})
        
        while self.current_index < len(self.script):
            while not self.is_playing:
                await asyncio.sleep(0.5)

            # Check for Injected Events first
            while not self._eventQueue.empty():
                ext_event = await self._eventQueue.get()
                if isinstance(ext_event, GodEventAction):
                    await self._apply_god_action(ext_event)
                else:
                    await self._handle_event_step(ext_event, is_injected=True)

            # Normal script event
            current_event = self.script[self.current_index]
            if self.performance_id:
                self.db.update_performance_status(self.performance_id, "running", self.current_index)
            
            # Broadcast scenario update (timeline progress)
            await self.broadcast({
                "type": "scenario_status",
                "events": [s.model_dump() for s in self.script],
                "current_event_idx": self.current_index
            })

            await self._handle_event_step(current_event)
            
            self.current_index += 1
            await asyncio.sleep(2)

        self.is_playing = False
        await self.broadcast({"type": "system", "content": "🎬 表演谢幕！"})

    async def _invoke_director_adaptation(self, previous_event: ScriptEvent, summary: str):
        """
        Calls the Director AI to adapt the next event based on the summary.
        """
        # 1. Check if there is a next event
        if self.current_index + 1 >= len(self.script):
            logger.info("End of script reached, no adaptation needed.")
            return

        next_event_idx = self.current_index + 1
        original_next_event = self.script[next_event_idx]
        
        logger.info(f"Director Adaptation triggered. Adapting event {next_event_idx}...")
        await self.broadcast({"type": "stage_direction", "content": "🤔 导演正在根据刚才的剧情调整剧本..."})
        await self.broadcast_debug(f"🎬 Director is adapting event {next_event_idx}...")

        try:
            # We need an LLM client for the Director. Ideally pass it in or use a default.
            # For now, pick the first available actor's client as a proxy or use a dedicated one.
            # In a real system, Director has its own config. 
            # Strategy: Look for an actor named "Director" or "Host", otherwise pick the one with the strongest model (e.g. gpt-4)
            director_client = None
            
            # Priority 1: Explicit "Director" actor
            if "Director" in self.llm_clients:
                director_client = self.llm_clients["Director"]
            else:
                # Priority 2: Find any client using gpt-4
                for name, client in self.llm_clients.items():
                    if "gpt-4" in client.model_name.lower():
                        director_client = client
                        break
                
                # Priority 3: Fallback to first available
                if not director_client:
                    director_client = next(iter(self.llm_clients.values()), None)

            if not director_client:
                logger.error("No LLM client available for Director.")
                return

            # Instantiate ScriptGenerator (stateless for now)
            # We assume the model name in client is sufficient.
            generator = ScriptGenerator(director_client.client, director_client.model_name)
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            theme = self.world_bible.get("theme", "Unknown Theme")
            if not theme: theme = "通用场景"

            # Prepare current plan dict
            current_plan = {
                "Time": original_next_event.timeline,
                "Event": original_next_event.event,
                "Goal": original_next_event.goal
            }
            
            adapted_data = await loop.run_in_executor(
                None, 
                lambda: generator.adapt_script(summary, current_plan, theme, available_cast=list(self.actors.keys()))
            )
            
            # Update the script!
            if adapted_data:
                # Merge back into ScriptEvent
                # We update the fields. We keep 'characters' and 'location' from original or leave them?
                # The generator only returns Time, Event, Goal.
                # So we update those.
                original_next_event.timeline = adapted_data.get("Time", original_next_event.timeline)
                original_next_event.event = adapted_data.get("Event", original_next_event.event)
                original_next_event.goal = adapted_data.get("Goal", original_next_event.goal)
                
                # Also update description if possible, but generator doesn't return description yet?
                # Wait, ScriptEvent has 'description' but generator returns 'Event' (which maps to description usually?)
                # In ScriptGenerator._to_dataframe, 'Event' is usually the description/content.
                original_next_event.description = adapted_data.get("Event", original_next_event.description)

                logger.info(f"Event {next_event_idx} adapted: {original_next_event.goal}")
                await self.broadcast({"type": "stage_direction", "content": f"💡 导演已更新下一幕: {original_next_event.event}"})
                await self.broadcast_debug(f"✅ Director updated event {next_event_idx}")
                
                # Persist change?
                if self.performance_id:
                     # Update DB (simplified, just log it)
                     self.db.log_event(self.performance_id, "DIRECTOR", "script_update", f"Updated Event {next_event_idx}: {original_next_event.event}")

        except Exception as e:
            logger.error(f"Director Adaptation failed: {e}")
            await self.broadcast({"type": "stage_direction", "content": "⚠️ 导演思考卡顿，继续按原计划进行。"})
            await self.broadcast_debug(f"❌ Director Error: {e}")


    async def _handle_event_step(self, event_data: Any, is_injected: bool = False):
        logger.info(f"Handling event step: {event_data.event if not is_injected else 'Injected'}")
        await self.broadcast_debug(f"🎬 Scene Started: {event_data.event}")
        
        # Track scene chat history for post-analysis
        # Link local variable to class member so user messages are seen
        if self.is_fresh_start:
             # Preserve existing messages (e.g. user trigger message) for the first scene
             self.is_fresh_start = False
             logger.info(f"Fresh start: Preserving {len(self.active_scene_chat_history)} messages.")
        else:
             self.active_scene_chat_history = []
             
        scene_chat_history = self.active_scene_chat_history
        
        if is_injected:
            if isinstance(event_data, dict) and "target" in event_data:
                desc = f"【突发事件】: {event_data['content']}"
                chars = [event_data['target']] if event_data['target'] in self.actors else []
            else:
                desc = event_data
                chars = list(self.actors.keys()) # Everyone reacts to God
            loc = "Current"
        else:
            desc = event_data.description
            # Robust character splitting (supports ; , and Chinese comma)
            raw_chars = event_data.characters
            if not raw_chars:
                chars = []
            else:
                chars = [c.strip() for c in re.split(r'[;,,，]', raw_chars) if c.strip()]
            
            loc = event_data.location
            msg = f"📍 {loc} | {event_data.timeline}\n**{event_data.event}**\n*{desc}*"
            if self.performance_id:
                self.db.log_event(self.performance_id, "SYSTEM", "stage_direction", msg)
            await self.broadcast({
                "type": "stage_direction",
                "content": msg
            })

            # --- [NEW] Start Conversation Loop ---
            current_turn = 0
            max_turns = event_data.max_turns
            scene_ended = False
            
            # Everyone who is in this scene (from "characters" field)
            active_actors = [c for c in chars if c in self.actors]
            
            # Fallback: If no specific actors found (or empty), use ALL available actors
            if not active_actors:
                logger.warning(f"No matching actors found for chars '{chars}'. Using all actors.")
                active_actors = list(self.actors.keys())
            
            if not active_actors:
                logger.error("No actors available at all! Skipping event.")
                await self.broadcast({"type": "system", "content": "⚠️ 当前无可用演员，跳过此幕。"})
                return

            logger.info(f"Active Actors for event: {active_actors}")
            await self.broadcast_debug(f"👥 Active Actors: {active_actors}")
            
            last_speaker_idx = -1
            consecutive_silence_count = 0
            prev_speaker_name = None
            consecutive_speech_count = 0

            while current_turn < max_turns and not scene_ended:
                # --- God Mode: Pause Check ---
                while not self.is_playing:
                    await asyncio.sleep(0.5)

                # --- God Mode: Check for Injected Events (Mid-scene) ---
                while not self._eventQueue.empty():
                    ext_event = await self._eventQueue.get()
                    
                    if isinstance(ext_event, GodEventAction):
                        await self._apply_god_action(ext_event)
                    elif isinstance(ext_event, dict) and "target" in ext_event:
                        # Targeted Event
                        target_actor = ext_event["target"]
                        content = ext_event["content"]
                        if target_actor in self.actor_memories:
                            # Inject into memory immediately so it's picked up in next context
                            self.actor_memories[target_actor].add(f"【突发事件】: {content}")
                            logger.info(f"Injected event for {target_actor}: {content}")
                            await self.broadcast_debug(f"⚡ Injected to {target_actor}: {content}")
                    else:
                        # Global Event (String)
                        msg = f"⚡ [突发指令]: {ext_event}"
                        # Add to everyone's memory
                        for mb in self.actor_memories.values():
                            mb.add(msg)
                        await self.broadcast({"type": "stage_direction", "content": msg})

                # 1. Select Speaker (Round Robin)
                last_speaker_idx = (last_speaker_idx + 1) % len(active_actors)
                char_name = active_actors[last_speaker_idx]
                
                # Anti-Monopoly Check
                if char_name == prev_speaker_name and consecutive_speech_count >= 2:
                    logger.info(f"Actor {char_name} skipped (Anti-Monopoly rule).")
                    await asyncio.sleep(0.1)
                    continue

                actor = self.actors[char_name]
                crew_actor = self.crew_actors[char_name]
                m_bank = self.actor_memories[char_name]

                logger.info(f"Preparing turn {current_turn} for {char_name}")

                # 2. Build Context
                blackboard_facts = self.blackboard.get_all_facts()
                stage_rules = StageRules(self.stage_type)
                
                context_memories = m_bank.get_recent(5)
                
                context = {
                    "event": event_data.event,
                    "description": desc,
                    "goal": event_data.goal,
                    "memories": context_memories,
                    "chat_history": scene_chat_history[-5:],
                    "stage_directives": stage_rules.get_stage_instructions(char_name, ", ".join(active_actors)),
                    "blackboard_facts": blackboard_facts
                }

                try:
                    # Execute CrewAI Agent
                    await self.broadcast({"type": "thinking", "actor": char_name})
                    await self.broadcast_debug(f"🤔 {char_name} is thinking...")
                    act_data = await asyncio.to_thread(crew_actor.perform, context)
                    
                    content = act_data.get("content", "...")
                    action = act_data.get("action", "")
                    finished = act_data.get("is_finished", False)
                    willingness = act_data.get("willingness", 5)
                    thought = act_data.get("thought", "")
                    
                    # Enhanced Debug: Show thought process or error details
                    await self.broadcast_debug(f"🗣️ {char_name} Raw: W={willingness} | {content[:30]}...")
                    if thought:
                        await self.broadcast_debug(f"💭 Thought: {thought[:100]}...")

                    # --- Willingness Logic ---
                    is_pass = (
                        content.strip() == "[PASS]" or 
                        (isinstance(willingness, int) and willingness < 3 and "[PASS]" in content) or
                        (not content.strip() and not action.strip())
                    )

                    if is_pass:
                        logger.info(f"Actor {char_name} passed (W: {willingness}).")
                        await self.broadcast_debug(f"⏭️ {char_name} Passed (Willingness: {willingness})")
                        consecutive_silence_count += 1
                        
                        # "Cold Field" Logic: If everyone passes (or willingness is low)
                        # We use len(active_actors) as the threshold. If everyone has passed once consecutively, scene ends.
                        if consecutive_silence_count >= len(active_actors):
                            logger.info("❄️ Cold Field detected (Everyone passed). Ending scene.")
                            await self.broadcast({"type": "stage_direction", "content": "❄️ 话题逐渐冷场..."})
                            scene_ended = True
                        continue
                    else:
                        consecutive_silence_count = 0
                    
                    # Update Anti-Monopoly
                    if char_name == prev_speaker_name:
                        consecutive_speech_count += 1
                    else:
                        prev_speaker_name = char_name
                        consecutive_speech_count = 1

                    # --- Special Interactions (Pat, Revoke) Parsing ---
                    if "[撤回]" in content or "[REVOKE]" in content or "[撤回]" in action:
                         self.blackboard.remove_last_dialogue(char_name)
                         await self.broadcast({"type": "revoke", "name": char_name})
                         if self.performance_id:
                            self.db.log_event(self.performance_id, char_name, "system", f"{char_name} 撤回了一条消息")
                         content = "" # Don't speak
                         action = ""  # Clear action to prevent dialogue broadcast

                    if content or action:
                        if content and action:
                            full_msg = f"{content} ({action})"
                        elif action:
                            full_msg = f"({action})"
                        else:
                            full_msg = content

                        if self.performance_id:
                            self.db.log_event(self.performance_id, char_name, "dialogue", full_msg)
                        
                        msg_obj = {
                            "type": "dialogue",
                            "name": char_name,
                            "content": content,
                            "action": action,
                            "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={char_name}",
                            "thought": thought,
                            "willingness": willingness
                        }
                        await self.broadcast(msg_obj)
                        
                        # Store raw content and action separately for cleaner context
                        scene_chat_history.append({
                            "role": "user", 
                            "name": char_name, 
                            "content": content,
                            "action": action
                        })
                        self.blackboard.add_dialogue(char_name, full_msg)
                        m_bank.add(f"在 {event_data.event} 中说: {full_msg}")
                    
                    if finished:
                        scene_ended = True
                        logger.info(f"Actor {char_name} signalled end of scene.")
                        
                except Exception as e:
                    logger.error(f"Actor error: {e}")
                    await self.broadcast_debug(f"❌ Actor Error: {e}")
                
                current_turn += 1
                await asyncio.sleep(1) # Pacing
            
            # --- [NEW] Post-Scene Analysis & Memory Consolidation ---
            if not is_injected and scene_chat_history:
                await self.broadcast({"type": "stage_direction", "content": "🕵️ 剧场书记官正在记录本幕摘要..."})
                try:
                    # 1. Generate Scene Summary (Objective)
                    analyst_client = next(iter(self.llm_clients.values()), None)
                    if analyst_client:
                         analyst = CrewPostSceneAnalyst(analyst_client.client, analyst_client.model_name)
                         
                         context = {
                             "theme": self.world_bible.get("theme", "General"),
                             "current_event": event_data.event
                         }
                         
                         loop = asyncio.get_event_loop()
                         analysis_result = await loop.run_in_executor(
                             None,
                             lambda: analyst.analyze(scene_chat_history, context)
                         )
                         
                         summary = analysis_result.get("summary", "")
                         new_facts = analysis_result.get("fact_updates", {}).get("new_facts", [])
                         
                         if summary:
                             self.blackboard.add_fact(f"Scene Summary: {summary}", "history")
                             if self.performance_id:
                                 self.db.log_event(self.performance_id, "SYSTEM", "summary", f"【本幕总结】{summary}")
                                 await self.broadcast({"type": "stage_direction", "content": f"📜 本幕总结: {summary}"})
                         
                         # 2. Memory Consolidation for Each Actor
                         # Ideally run in parallel, but for stability sequential here
                         for name, m_bank in self.actor_memories.items():
                            # Simple consolidation: Add the scene summary to their memory
                            m_bank.add_long_term(f"In scene '{event_data.event}', I remember: {summary}")
                            # In a full version, we would ask each actor to reflect personally.
                             
                         # 3. Director Adapts Next Scene (The "Rise and Fall" Logic)
                         if summary:
                             await self._invoke_director_adaptation(event_data, summary)
                             
                except Exception as e:
                    logger.error(f"Post-scene analysis failed: {e}")

            
            # Legacy loop removed


    async def _handle_ws_message(self, ws: WebSocket, msg: str):
        import json
        try:
            data = json.loads(msg)
            msg_type = data.get("type")

            # Verbose debug for all incoming messages if debug mode is on
            if self.debug_mode and msg_type != "heartbeat":
                 await self.broadcast_debug(f"📥 WS Recv: {msg_type}")
            
            if msg_type == "get_members":
                # Return current actors + User
                member_list = []
                # Teachers/Actors
                for name, cfg in self.actors.items():
                    member_list.append({
                        "name": name,
                        "isUser": False,
                        "avatar": "🤖", 
                        "isManager": False
                    })
                # Add implicit user if connected? Or user adds themselves in frontend?
                # Frontend usually has "Gaia" hardcoded, but we can confirm.
                await ws.send_json({
                    "type": "members_list",
                    "members": member_list,
                    "group_name": self.world_bible.get("group_name", "AI Theater Group")
                })
            
            elif msg_type == "get_history":
                # Send recent blackboard history
                history = self.blackboard.get_recent_dialogue_struct(50)
                await ws.send_json({
                    "type": "history",
                    "messages": history
                })
                
            elif msg_type == "setup":
                # Frontend sending setup config? Usually init is done via REST.
                # But maybe we accept it here too.
                pass
                
            elif msg_type == "start":
                await self.start()
                
            elif msg_type == "stop":
                self.pause()
                
            elif msg_type == "update_settings":
                if "group_name" in data:
                    self.world_bible["group_name"] = data["group_name"]
                    # Persist?
                    pass

            elif msg_type == "toggle_debug":
                if "enabled" in data:
                    self.debug_mode = data["enabled"]
                else:
                    self.debug_mode = not self.debug_mode
                
                state = "ON" if self.debug_mode else "OFF"
                logger.info(f"Debug Mode toggled {state}")
                await self.broadcast_debug(f"🐞 Debug Mode {state}")
                # Confirm to frontend
                await self.broadcast({"type": "debug_status", "enabled": self.debug_mode})

            elif msg_type == "user_message":
                # Handle User Input
                user_name = data.get("name", "Gaia")
                content = data.get("content", "")
                
                await self.broadcast_debug(f"📨 Received User Message: {content[:50]}")
                
                if content:
                    # 1. Add to Blackboard
                    self.blackboard.add_dialogue(user_name, content)
                    
                    # 2. Log to DB
                    if self.performance_id:
                        self.db.log_event(self.performance_id, user_name, "dialogue", content)
                    
                    # 3. Broadcast to all clients
                    await self.broadcast({
                        "type": "dialogue", 
                        "actor": user_name, 
                        "content": content,
                        "is_user": True,
                        "nickname": user_name,
                        "avatar": f"https://api.dicebear.com/7.x/micah/svg?seed={user_name}" # Default or from user config
                    })

                    # 3.1 Add to active scene history so actors can see it!
                    self.active_scene_chat_history.append({
                        "role": "user",
                        "name": user_name,
                        "content": content,
                        "action": ""
                    })
                    
                    # 4. Auto-start if not playing
                    if not self.is_playing:
                        logger.info("User message received while paused/stopped. Auto-starting...")
                        
                        # If script is finished, append a new "User Interaction" event to keep the loop going
                        if self.current_index >= len(self.script):
                            logger.info("Script finished. Appending new event for user interaction.")
                            new_event = ScriptEvent(
                                timeline="User Interaction",
                                event="User Spoke",
                                characters=",".join(self.actors.keys()),
                                description=f"User ({user_name}) said: {content}. Actors should respond naturally.",
                                location="Current Location",
                                goal="Respond to user",
                                max_turns=5
                            )
                            self.script.append(new_event)
                            # Do not increment current_index manually, the loop will handle it
                        
                        self.is_playing = True
                        await self.start()
                    elif self.is_playing and self.current_index >= len(self.script):
                         # Playing but reached end? Extend script
                         logger.info("Script finished while playing. Appending new event.")
                         new_event = ScriptEvent(
                                timeline="User Interaction",
                                event="User Spoke",
                                characters=",".join(self.actors.keys()),
                                description=f"User ({user_name}) said: {content}. Actors should respond naturally.",
                                location="Current Location",
                                goal="Respond to user",
                                max_turns=5
                         )
                         self.script.append(new_event)

        except Exception as e:
            logger.error(f"WS Message Handle Error: {e}")

    # --- [New] Helper to send message ---
    async def send_to(self, ws: WebSocket, data: Dict):
        try:
            await ws.send_json(data)
        except:
            pass

manager = StageManager()

@app.websocket("/ws/{room_id}")
async def ws_theater(websocket: WebSocket, room_id: str):
    await manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            await manager._handle_ws_message(websocket, msg)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/init")
async def api_init(req: InitRequest):
    logger.info(f"Received init request with {len(req.actors)} actors and {len(req.script)} events.")
    try:
        manager.initialize(req)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error during initialization: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def api_status():
    return {
        "is_playing": manager.is_playing,
        "current_index": manager.current_index,
        "total_events": len(manager.script),
        "world_bible": manager.world_bible
    }

@app.post("/update_scenario")
async def api_update_scenario(events: List[Dict[str, str]]):
    """Update upcoming script events."""
    try:
        new_events = [ScriptEvent(**e) for e in events]
        # Keep historical events, replace matching or adding new ones
        # For simplicity, we currently replace everything from the next index onwards
        manager.script = manager.script[:manager.current_index + 1] + new_events[manager.current_index + 1:]
        return {"status": "ok", "count": len(manager.script)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/control")
async def api_control(action: str, value: Optional[int] = None, content: Optional[str] = None):
    if action == "start": await manager.start()
    elif action == "pause": manager.pause()
    elif action == "resume": await manager.start()
    elif action == "jump": manager.jump(value or 0)
    elif action == "inject": await manager.inject_event(content or "")
    return {"status": "ok"}

@app.post("/add_fact")
async def api_add_fact(fact: str, category: str = "general"):
    manager.blackboard.add_fact(fact, category)
    if manager.performance_id:
        manager.db.log_event(manager.performance_id, "SYSTEM", "system", f"📌 [全局事实更新]: {fact}")
    await manager.broadcast({"type": "system", "content": f"📌 [全局事实更新]: {fact}"})
    return {"status": "ok"}

# --- God Mode Endpoints ---
class InjectRequest(BaseModel):
    actor_name: Optional[str] = None
    content: str

class TimeTravelRequest(BaseModel):
    new_time: str

@app.post("/god_mode/inject")
async def god_inject(req: InjectRequest):
    if req.actor_name:
        await manager.inject_targeted_event(req.actor_name, req.content)
    else:
        await manager.inject_event(req.content)
    return {"status": "ok"}

@app.post("/god_mode/time_travel")
async def god_time_travel(req: TimeTravelRequest):
    await manager.time_travel(req.new_time)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
