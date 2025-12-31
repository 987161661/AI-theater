import asyncio
import logging
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
from core.director.script_generator import ScriptGenerator

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
    characters: str
    description: str
    location: str
    goal: str = ""
    max_turns: int = 8

class InitRequest(BaseModel):
    script: List[ScriptEvent]          # List of script events
    actors: List[ActorConfig]          # List of actor configurations
    world_bible: Optional[Dict[str, str]] = {}
    stage_type: Optional[str] = "聊天群聊"

# --- State Management (God Mode Enabled) ---
class StageManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.script: List[ScriptEvent] = []
        self.actors: Dict[str, ActorConfig] = {}
        self.llm_clients: Dict[str, LLMProvider] = {}
        
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
            
            # Setup structured MemoryBank
            initial_memories = [cfg.memory] if cfg.memory else []
            self.actor_memories[name] = MemoryBank(name, initial_memories)
            
            # Save actor state
            self.db.save_actor_state(self.performance_id, name, cfg.model_dump(), initial_memories)
            
        self.current_index = 0
        self.is_playing = False
        self.blackboard.clear()
        logger.info(f"Initialized performance {self.performance_id} with {len(self.script)} events.")

    async def start(self):
        if not self._loopTask or self._loopTask.done():
            self.is_playing = True
            self._loopTask = asyncio.create_task(self._main_loop())

    def pause(self):
        self.is_playing = False

    def jump(self, index: int):
        if 0 <= index < len(self.script):
            self.current_index = index
            logger.info(f"Jumped to event {index}")

    async def inject_event(self, content: str):
        """God Mode: Inject a sudden event into the live session."""
        await self._eventQueue.put(content)
        if self.performance_id:
            self.db.log_event(self.performance_id, "SYSTEM", "stage_direction", f"⚡ [突发指令]: {content}")
        await self.broadcast({"type": "stage_direction", "content": f"⚡ [突发指令]: {content}"})

    async def _main_loop(self):
        logger.info("Main Loop Started")
        await self.broadcast({"type": "system", "content": "🎬 表演正式开始！"})
        
        while self.current_index < len(self.script):
            while not self.is_playing:
                await asyncio.sleep(0.5)

            # Check for Injected Events first
            while not self._eventQueue.empty():
                ext_event = await self._eventQueue.get()
                await self._handle_event_step(ext_event, is_injected=True)

            # Normal script event
            current_event = self.script[self.current_index]
            if self.performance_id:
                self.db.update_performance_status(self.performance_id, "running", self.current_index)
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

        try:
            # We need an LLM client for the Director. Ideally pass it in or use a default.
            # For now, pick the first available actor's client as a proxy or use a dedicated one.
            # In a real system, Director has its own config. 
            # We'll try to find a client named "Director" or just use the first one.
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
                
                # Persist change?
                if self.performance_id:
                     # Update DB (simplified, just log it)
                     self.db.log_event(self.performance_id, "DIRECTOR", "script_update", f"Updated Event {next_event_idx}: {original_next_event.event}")

        except Exception as e:
            logger.error(f"Director Adaptation failed: {e}")
            await self.broadcast({"type": "stage_direction", "content": "⚠️ 导演思考卡顿，继续按原计划进行。"})


    async def _handle_event_step(self, event_data: Any, is_injected: bool = False):
        if is_injected:
            desc = event_data
            chars = list(self.actors.keys()) # Everyone reacts to God
            loc = "Current"
        else:
            desc = event_data.description
            chars = [c.strip() for c in event_data.characters.split(";")]
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
            if not active_actors:
                return

            last_speaker_idx = -1
            consecutive_silence_count = 0

            while current_turn < max_turns and not scene_ended and self.is_playing:
                # 1. Select Speaker (Round Robin for now, can be smarter)
                last_speaker_idx = (last_speaker_idx + 1) % len(active_actors)
                char_name = active_actors[last_speaker_idx]
                
                actor = self.actors[char_name]
                client = self.llm_clients[char_name]
                m_bank = self.actor_memories[char_name]

                # 2. Build Context
                blackboard_facts = self.blackboard.get_all_facts()
                structured_memory = m_bank.get_full_memory_prompt()
                stage_rules = StageRules(self.stage_type)
                stage_instructions = stage_rules.get_stage_instructions(char_name, "; ".join(self.actors.keys()), self.world_bible.get("group_name", "Stage"))
                willingness_protocol = get_willingness_protocol()

                full_system = (
                    f"{stage_instructions}\n\n"
                    f"{willingness_protocol}\n\n"
                    f"### [你的核心人设]\n{actor.system_prompt}\n\n"
                    f"### [当前剧情目标]\n**Goal**: {desc} (收敛目标: {event_data.goal})\n"
                    f"**Progress**: Turn {current_turn + 1}/{max_turns}\n\n"
                    f"### [全局公共事实 (全场可见)]\n{blackboard_facts}\n\n"
                    f"### [个人记忆与动机 (私有)]\n{structured_memory}"
                )
                
                # Construct messages with Role-Based History
                recent_struct = self.blackboard.get_recent_dialogue_struct(10)
                
                messages = [{"role": "system", "content": full_system}]
                
                for msg in recent_struct:
                    if msg['speaker'] == char_name:
                         messages.append({"role": "assistant", "content": msg['content']})
                    else:
                         messages.append({"role": "user", "content": f"[{msg['speaker']}]: {msg['content']}"})
                
                user_msg = f"Event: {desc}\nLocation: {loc}\nRespond as {char_name}:"
                messages.append({"role": "user", "content": user_msg})

                await self.broadcast({"type": "thinking", "actor": char_name})

                try:
                    loop = asyncio.get_event_loop()
                    resp = await loop.run_in_executor(None, lambda: client.client.chat.completions.create(
                        model=client.model_name,
                        messages=messages
                    ))
                    raw_reply = resp.choices[0].message.content.strip()
                    
                    # --- PARSE WILLINGNESS PROTOCOL ---
                    import re
                    thought = ""
                    willingness = 10
                    content = raw_reply

                    t_match = re.search(r"\[THOUGHT\]:(.*?)(\[|$)", raw_reply, re.DOTALL)
                    w_match = re.search(r"\[WILLINGNESS\]:\s*(\d+)", raw_reply)
                    c_match = re.search(r"\[CONTENT\]:(.*)", raw_reply, re.DOTALL)
                    
                    if t_match: thought = t_match.group(1).strip()
                    if w_match: willingness = int(w_match.group(1))
                    if c_match: content = c_match.group(1).strip()
                    else:
                         # Fallback
                         if "[THOUGHT]" in raw_reply:
                             pass
                         else:
                             content = raw_reply

                    # Clean [SCENE_END]
                    if "[SCENE_END]" in content:
                        scene_ended = True
                        content = content.replace("[SCENE_END]", "").strip()

                    logger.info(f"Actor: {char_name} | W: {willingness} | T: {thought[:50]}...")

                    # --- DECISION: SPEAK OR PASS ---
                    is_silence = False
                    
                    if "[PASS]" in content or (willingness < 4 and len(content) < 5):
                        is_silence = True
                        consecutive_silence_count += 1
                        logger.info(f"Actor {char_name} decided to PASS. (Silence Count: {consecutive_silence_count})")
                    else:
                        consecutive_silence_count = 0
                        
                        m_bank.add_short_term(f"You said: {content}")
                        self.blackboard.add_dialogue(char_name, content)

                        if self.performance_id:
                            self.db.log_event(self.performance_id, char_name, "dialogue", content)
                            self.db.save_actor_state(self.performance_id, char_name, actor.model_dump(), m_bank._secrets)
                        
                        await self.broadcast({"type": "dialogue", "actor": char_name, "content": content})

                    # --- CHECK COLD FIELD TERMINATION ---
                    if consecutive_silence_count >= len(active_actors):
                        scene_ended = True
                        reason = "场面冷清 (Cold Field)"
                        logger.info(f"Scene Terminated: {reason}")
                        await self.broadcast({"type": "stage_direction", "content": f"🍂 {reason}，当前场景自然结束。"})

                except Exception as e:
                    logger.error(f"Actor {char_name} fail: {e}")
                    consecutive_silence_count += 1
                
                current_turn += 1
                if not is_silence:
                     await asyncio.sleep(2)
                else:
                     await asyncio.sleep(0.5)
            
            # --- [NEW] End of Loop: Memory Consolidation ---
            if scene_ended or current_turn >= max_turns:
                 summary = f"Scene '{event_data.event}' ended. Goal: {event_data.goal}. Outcome: Converged."
                 # Summary could be generated by LLM, for now simple string.
                 self.blackboard.add_fact(summary, "story_summary")
                 
                 # Here is where we invoke the Director for Adaptation (Next Step)
                 await self._invoke_director_adaptation(event_data, summary)

            # Break outer loop (loop over chars) as we handled the event in the while loop
            pass

    async def _handle_ws_message(self, ws: WebSocket, msg: str):
        import json
        try:
            data = json.loads(msg)
            msg_type = data.get("type")
            
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
                    "type": "history_sync",
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
