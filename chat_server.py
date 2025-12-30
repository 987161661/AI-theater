import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn

from core.llm_provider import LLMProvider
from core.state.db_manager import DBManager
from core.state.performance_blackboard import PerformanceBlackboard
from core.actor.memory_bank import MemoryBank

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StageServer")

app = FastAPI()

# --- Models ---
class ActorConfig(BaseModel):
    name: str
    model_config: Dict[str, str]
    system_prompt: str
    memory: str = ""

class ScriptEvent(BaseModel):
    timeline: str
    event: str
    characters: str
    description: str
    location: str

class InitRequest(BaseModel):
    script: List[Dict[str, str]]
    actors: List[ActorConfig]
    world_bible: Dict[str, str] = {}

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
        self.script = [ScriptEvent(**item) for item in data.script]
        self.actors = {a.name: a for a in data.actors}
        self.world_bible = data.world_bible
        
        # Persist to DB
        script_id = self.db.save_script("Live Performance", [s.model_dump() for s in self.script])
        self.performance_id = self.db.create_performance(script_id, self.world_bible)
        
        for name, cfg in self.actors.items():
            m = cfg.model_config
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

        for char_name in chars:
            if char_name not in self.actors: continue
            if not self.is_playing: break

            actor = self.actors[char_name]
            client = self.llm_clients[char_name]
            m_bank = self.actor_memories[char_name]
            
            # 1. Combine System Prompt with Memory & Blackboard
            blackboard_facts = self.blackboard.get_all_facts()
            structured_memory = m_bank.get_full_memory_prompt()
            
            full_system = (
                f"{actor.system_prompt}\n\n"
                f"### [全局公共事实 (全场可见)]\n{blackboard_facts}\n\n"
                f"### [个人记忆与动机 (私有)]\n{structured_memory}"
            )
            user_msg = f"Event: {desc}\nLocation: {loc}\nRespond as {char_name}:"

            await self.broadcast({"type": "thinking", "actor": char_name})
            
            try:
                loop = asyncio.get_event_loop()
                # Use executor for sync LLM call
                resp = await loop.run_in_executor(None, lambda: client.client.chat.completions.create(
                    model=client.model_name,
                    messages=[{"role": "system", "content": full_system}, {"role": "user", "content": user_msg}]
                ))
                reply = resp.choices[0].message.content
                
                # Update Memory & Persistence
                m_bank.add_short_term(f"Event: {desc} -> You replied: {reply}")
                if self.performance_id:
                    self.db.log_event(self.performance_id, char_name, "dialogue", reply)
                    self.db.save_actor_state(self.performance_id, char_name, actor.model_dump(), m_bank._secrets)
                
                await self.broadcast({"type": "dialogue", "actor": char_name, "content": reply})
            except Exception as e:
                logger.error(f"Actor {char_name} fail: {e}")

            await asyncio.sleep(1.5)

manager = StageManager()

@app.websocket("/ws/theater")
async def ws_theater(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/init")
async def api_init(req: InitRequest):
    manager.initialize(req)
    return {"status": "ok"}

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
