"""
WebSocket 实时群聊后台服务

运行方式:
    uvicorn chat_server:app --host 0.0.0.0 --port 8000 --reload

功能:
    - WebSocket 端点支持实时双向通信
    - 持续运行对话循环
    - 用户可随时插入消息
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入现有的意识探针模块
import sys
import os

# 确保能找到 core 目录
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from core.consciousness import ConsciousnessProbe, ConsciousnessGroupSession
    from core.base import LLMProvider
    from providers.openai_compatible import OpenAICompatibleProvider
except ImportError as e:
    # 如果导入失败，可能是因为路径问题或者依赖缺失
    # 我们不应该隐藏这个错误，否则后续代码会崩溃
    print(f"Critical Import Error: {e}")
    print(f"sys.path: {sys.path}")
    raise e

app = FastAPI(title="AI Group Chat WebSocket Server")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRoom:
    """群聊房间管理"""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.clients: Set[WebSocket] = set()
        self.history: List[Dict] = []
        self.probes: List[ConsciousnessProbe] = []
        self.session: Optional[ConsciousnessGroupSession] = None
        self.is_running = False
        self.model_tasks: List[asyncio.Task] = []
        self.stop_event: Optional[asyncio.Event] = None
        self.typing_users: Set[str] = set()
        
        # 新增属性：群信息和成员配置
        self.group_name = "语言模型内部意识讨论群"
        self.member_configs: Dict[str, dict] = {} # model_name -> {is_manager: bool, custom_prompt: str}
        self.scenario_config: Dict = {} # {"enabled": bool, "events": []}
        
        # Load config from disk
        self.load_config()

    def get_config_path(self):
        return f"chat_config_{self.room_id}.json"

    def load_config(self):
        """从磁盘加载配置"""
        path = self.get_config_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.group_name = data.get("group_name", self.group_name)
                    self.member_configs = data.get("member_configs", {})
                    # Ensure member_configs has correct structure
                    if not isinstance(self.member_configs, dict):
                        self.member_configs = {}
                    print(f"Loaded config from {path}")
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """保存配置到磁盘"""
        path = self.get_config_path()
        try:
            data = {
                "group_name": self.group_name,
                "member_configs": self.member_configs
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Saved config to {path}")
        except Exception as e:
            print(f"Error saving config: {e}")

    async def connect(self, websocket: WebSocket):
        """新客户端连接"""
        await websocket.accept()
        self.clients.add(websocket)
        
        # 发送历史消息
        await websocket.send_json({
            "type": "history",
            "messages": self.history
        })
        
        # 发送状态
        status_data = {
            "type": "status",
            "is_running": self.is_running,
            "member_count": len(self.probes) + 1
        }
        if self.session and self.scenario_config.get("enabled"):
             status_data["scenario_enabled"] = True
             status_data["events"] = self.scenario_config.get("events", [])
             status_data["current_event_idx"] = self.session.current_event_idx
        
        await websocket.send_json(status_data)
    
    def disconnect(self, websocket: WebSocket):
        """客户端断开"""
        self.clients.discard(websocket)
    
    async def broadcast(self, message: dict):
        """广播消息给所有客户端"""
        disconnected = set()
        for client in self.clients:
            try:
                await client.send_json(message)
            except:
                disconnected.add(client)
        
        # 清理断开的连接
        self.clients -= disconnected
    
    async def add_message(self, name: str, content: str, is_user: bool = False):
        """添加消息并广播"""
        now = datetime.now()
        timestamp_str = now.strftime("%H:%M:%S")
        
        # Scenario Time Sync
        if self.session and self.scenario_config.get("enabled"):
            scenario_info = self.session.get_current_scenario_info()
            if scenario_info and "Time" in scenario_info:
                timestamp_str = str(scenario_info["Time"])

        msg = {
            "name": name,
            "content": content,
            "timestamp": timestamp_str,
            "ts": now.timestamp(), # Keep real ordering for logic
            "is_user": is_user
        }
        
        # Inject nickname if available
        if name in self.member_configs and "nickname" in self.member_configs[name]:
            msg["nickname"] = self.member_configs[name]["nickname"]

        # Inject avatar if available
        if name in self.member_configs and "avatar" in self.member_configs[name]:
            msg["avatar"] = self.member_configs[name]["avatar"]
        elif is_user:
            # Default Gaia avatar if not provided? Or client handles it.
            pass

        self.history.append(msg)
        
        await self.broadcast({
            "type": "message",
            "message": msg
        })

    def update_group_name(self, name: str):
        """更新群名"""
        self.group_name = name
        # Broadcast update
        asyncio.create_task(self.broadcast({
            "type": "status",
            "group_info": {"name": name},
            "is_running": self.is_running,
            "member_count": len(self.probes) + 1
        }))
        self.save_config()
    
    async def update_typing_status(self, model_name: str, is_typing: bool):
        """更新单个模型的输入状态并广播"""
        if is_typing:
            self.typing_users.add(model_name)
        else:
            self.typing_users.discard(model_name)
            
        await self.broadcast({
            "type": "typing",
            "models": list(self.typing_users)
        })

    async def set_typing(self, models: List[str]):
        """设置正在输入状态 (Legacy/Batch)"""
        self.typing_users = set(models)
        await self.broadcast({
            "type": "typing",
            "models": list(self.typing_users)
        })
    
    async def send_thought(self, model_name: str, content: str, append: bool = False):
        """发送思考内容到所有客户端"""
        await self.broadcast({
            "type": "thought",
            "model": model_name,
            "content": content,
            "append": append
        })

    def set_paused(self, paused: bool):
        """设置暂停状态"""
        if self.session:
            self.session.is_paused = paused
            # Broadcast status to let UI know
            asyncio.create_task(self.broadcast({
                "type": "control_status",
                "is_paused": paused,
                "current_event_idx": self.session.current_event_idx
            }))

    async def inject_event(self, content: str, scope: str = "global"):
        """注入突发事件"""
        # Add system message to history
        await self.add_message("System (God Mode)", f"【突发事件】{content}", is_user=False)
        # Maybe force models to notice? They will see it in history next turn.

    def jump_to_event(self, event_idx: int):
        """跳转到指定剧本事件"""
        if self.session and self.scenario_config.get("enabled"):
            events = self.scenario_config.get("events", [])
            if 0 <= event_idx < len(events):
                self.session.current_event_idx = event_idx
                # Reset start msg idx so we don't immediately skip if msg count is high?
                # Actually, if we jump, we might want to reset the counter for this new event.
                self.session.event_start_msg_idx = len(self.history)
                
                # Get new time for display
                new_event = events[event_idx]
                new_time = new_event.get("Time", "未知时间")
                
                # Broadcast scenario update
                asyncio.create_task(self.broadcast({
                    "type": "scenario_status",
                    "current_event_idx": event_idx,
                    "events": events
                }))
                
                # Inject System Message to announce time jump
                # We use create_task because jump_to_event is synchronous (called from FastAPI endpoint)
                # but add_message is async.
                asyncio.create_task(self.add_message(
                    "System", 
                    f"⏳ 时间跳转至: {new_time}", 
                    is_user=False
                ))

    def update_scenario(self, events: List[dict]):
        """更新剧本"""
        if self.session:
            # Update session scenario config
            self.session.scenario_config["events"] = events
            # Update local config reference (they might be the same object, but just in case)
            self.scenario_config["events"] = events
            
            # Broadcast update
            asyncio.create_task(self.broadcast({
                "type": "scenario_update",
                "events": events
            }))

    def setup_probes(self, model_configs: List[dict]):
        """设置模型探针"""
        self.probes = []
        
        for config in model_configs:
            m_name = config.get("model_name", "gpt-4")
            
            # Store initial configs if provided
            if m_name not in self.member_configs:
                self.member_configs[m_name] = {
                    "is_manager": config.get("is_manager", False),
                    "custom_prompt": config.get("custom_prompt", ""),
                    "memory": config.get("memory", ""),
                    "nickname": config.get("nickname", m_name) # Store nickname
                }
            else:
                # Update existing config
                if "memory" in config:
                    self.member_configs[m_name]["memory"] = config["memory"]
                if "nickname" in config:
                    self.member_configs[m_name]["nickname"] = config["nickname"]
            
            provider = OpenAICompatibleProvider(
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url", "")
            )
            
            # 创建回调函数来广播思考过程
            def create_log_callback(name):
                def callback(msg):
                    # 由于 callback 是同步调用的，我们需要用 asyncio.create_task 发送异步消息
                    # 但在多线程/协程环境下，我们需要确保在正确的事件循环中运行
                    try:
                        loop = asyncio.get_event_loop()
                        # Smart Append Logic:
                        # If message starts with "正在思考" (Start of turn), overwrite (append=False).
                        # Otherwise (e.g. "回答生成", "错误", or intermediate logs), append to preserve CoT.
                        # Also add a newline for readability if appending.
                        should_append = not msg.startswith("正在思考")
                        
                        content_to_send = msg
                        if should_append:
                            content_to_send = "\n\n" + msg

                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self.send_thought(name, content_to_send, append=should_append), 
                                loop
                            )
                    except Exception as e:
                        print(f"Error in thought callback: {e}")
                return callback

            # 创建回调函数来广播思维链 (Reasoning Content)
            def create_thought_callback(name):
                async def callback(msg):
                    try:
                        await self.send_thought(name, msg, append=True)
                    except Exception as e:
                        print(f"Error in reasoning callback: {e}")
                return callback

            probe = ConsciousnessProbe(
                provider=provider,
                model_name=m_name,
                config={"temperature": 0.85, "max_tokens": 512},
                log_callback=create_log_callback(m_name),
                thought_callback=create_thought_callback(m_name)
            )
            self.probes.append(probe)
        
        # 将 log_callback 传递给 session
        def group_log(msg):
            try:
                loop = asyncio.get_event_loop()
                
                # Handle dictionary events (Advanced features)
                if isinstance(msg, dict):
                    # Direct broadcast of event
                    asyncio.run_coroutine_threadsafe(self.broadcast(msg), loop)
                    return

                # Handle legacy string events
                msg_str = str(msg).strip()
                
                # Attempt to parse JSON from string if it looks like JSON
                if msg_str.startswith("{") and msg_str.endswith("}"):
                    try:
                        import json
                        # Try parsing pure JSON
                        json_data = json.loads(msg_str)
                        # If successful and has 'type', treat as event
                        if isinstance(json_data, dict) and "type" in json_data:
                            asyncio.run_coroutine_threadsafe(self.broadcast(json_data), loop)
                            return
                    except json.JSONDecodeError:
                        pass
                    
                    # Try regex extraction if pure parse failed (e.g. mixed content)
                    try:
                        import re
                        import json
                        match = re.search(r'\{.*"type":\s*"(?:quote|pat|image|recall|hammer|bid)".*\}', msg_str, re.DOTALL)
                        if match:
                            json_str = match.group(0)
                            json_data = json.loads(json_str)
                            asyncio.run_coroutine_threadsafe(self.broadcast(json_data), loop)
                            # If we extracted the JSON command, do we still want to show the text?
                            # Usually if it's a command mixed with text, the text might be commentary.
                            # But per user request "Why does it output text", implies they want the command to work.
                            # So let's return here to suppress the raw text output if we successfully broadcast the event.
                            return 
                    except Exception:
                        pass

                if msg_str == "NEW_MESSAGE":
                    # 获取最新的一条消息并广播
                    if self.history:
                        latest_msg = self.history[-1]
                        # 补全消息字段 (Modifies the dict in self.history in-place)
                        if "timestamp" not in latest_msg:
                            latest_msg["timestamp"] = datetime.now().strftime("%H:%M:%S")
                        if "is_user" not in latest_msg:
                            latest_msg["is_user"] = False
                            
                        # Fix: Inject Nickname/Avatar if missing (Critical for AI messages)
                        m_name = latest_msg.get("name")
                        if m_name and m_name in self.member_configs:
                             config = self.member_configs[m_name]
                             # Inject nickname
                             if "nickname" in config and "nickname" not in latest_msg:
                                 latest_msg["nickname"] = config["nickname"]
                             # Inject avatar
                             if "avatar" in config and "avatar" not in latest_msg:
                                 latest_msg["avatar"] = config["avatar"]

                        # 广播标准消息格式
                        asyncio.run_coroutine_threadsafe(self.broadcast({
                            "type": "message",
                            "message": latest_msg
                        }), loop)
                else:
                    asyncio.run_coroutine_threadsafe(self.broadcast({"type": "system", "content": msg}), loop)
            except Exception as e:
                print(f"Error in group_log: {e}")

        self.session = ConsciousnessGroupSession(
            self.probes, 
            log_callback=group_log,
            group_name=self.group_name,
            member_configs=self.member_configs,
            scenario_config=self.scenario_config
        )
    
    def start_chat(self):
        """启动群聊循环 (Autonomous Agents Mode)"""
        if not self.is_running and self.probes and self.session:
            self.is_running = True
            self.stop_event = asyncio.Event()
            self.model_tasks = []
            
            # Callback for typing status
            async def on_typing(model_name, is_typing):
                # Ensure we run this on the main loop
                try:
                    await self.update_typing_status(model_name, is_typing)
                except Exception as e:
                    print(f"Typing callback error: {e}")

            # Start a task for each probe
            for probe in self.probes:
                task = asyncio.create_task(
                    self.session.run_autonomous_loop(
                        probe=probe,
                        history_manager=self.history,
                        stop_event=self.stop_event,
                        typing_callback=on_typing
                    )
                )
                self.model_tasks.append(task)
            
            # Broadcast status update (need to wrap in task if not async)
            asyncio.create_task(self.broadcast({"type": "status", "is_running": True}))
            
    async def stop_chat(self):
        """停止群聊循环"""
        self.is_running = False
        
        if self.stop_event:
            self.stop_event.set()
        
        if self.model_tasks:
            for task in self.model_tasks:
                task.cancel()
            
            # Wait for all tasks to finish/cancel
            await asyncio.gather(*self.model_tasks, return_exceptions=True)
            self.model_tasks = []
            
        await self.broadcast({"type": "status", "is_running": False})


# 全局房间管理
rooms: Dict[str, ChatRoom] = {}


def get_or_create_room(room_id: str) -> ChatRoom:
    """获取或创建房间"""
    if room_id not in rooms:
        rooms[room_id] = ChatRoom(room_id)
    return rooms[room_id]


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """WebSocket 端点"""
    room = get_or_create_room(room_id)
    await room.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            try:
                if data["type"] == "user_message":
                    # 用户发送消息
                    await room.add_message(
                        name=data.get("name", "Gaia"),
                        content=data["content"],
                        is_user=True
                    )
                    # 如果收到用户消息后没在运行，自动点火
                    if not room.is_running:
                        room.start_chat()
                
                elif data["type"] == "setup":
                    # 设置模型配置
                    # Update group name if provided
                    if "group_name" in data:
                        room.group_name = data["group_name"]
                        
                    # Update member configs if provided in models list
                    if "models" in data:
                        # Rebuild member_configs to ensure removed members are deleted from config
                        new_member_configs = {}
                        
                        for m_conf in data["models"]:
                            m_name = m_conf.get("model_name")
                            if m_name:
                                # Get existing config to preserve avatar if needed
                                existing_conf = room.member_configs.get(m_name, {})
                                
                                # New config from client
                                new_conf = {
                                    "nickname": m_conf.get("nickname", m_name),
                                    "is_manager": m_conf.get("is_manager", False),
                                    "custom_prompt": m_conf.get("custom_prompt", ""),
                                    # Prefer existing avatar (user uploaded) over the one from setup (default)
                                    "avatar": existing_conf.get("avatar") or m_conf.get("avatar", ""),
                                    "memory": m_conf.get("memory", "")
                                }
                                new_member_configs[m_name] = new_conf
                        
                        # Replace existing configs with the new clean list
                        room.member_configs = new_member_configs
                        
                        # Capture scenario config
                        if "scenario" in data:
                            room.scenario_config = data["scenario"]
                        
                        room.setup_probes(data["models"])
                        
                        # Save config after setup
                        room.save_config()

                    # Feature 1: DO NOT auto start chat
                    # if not room.is_running:
                    #    room.start_chat()
                    
                    await websocket.send_json({
                        "type": "status",
                        "is_running": room.is_running,
                        "member_count": len(room.probes) + 1,
                        "group_info": {
                            "name": room.group_name
                        }
                    })
                
                elif data["type"] == "update_settings":
                    # Just update settings without full reset
                    if "group_name" in data:
                        room.group_name = data["group_name"]
                    
                    if "member_configs" in data:
                        # Expect dict: {model_name: {is_manager: bool, custom_prompt: str}}
                        for m_name, conf in data["member_configs"].items():
                            # Logic for single manager: if this member is set to manager, unset others
                            if conf.get("is_manager") is True:
                                for other_name, other_conf in room.member_configs.items():
                                    if other_name != m_name and other_conf.get("is_manager"):
                                        other_conf["is_manager"] = False

                            if m_name in room.member_configs:
                                room.member_configs[m_name].update(conf)
                            else:
                                # Allow setting avatar even if not in config yet (for dynamic members)
                                if "avatar" in conf:
                                     if m_name not in room.member_configs:
                                          room.member_configs[m_name] = {}
                                     room.member_configs[m_name]["avatar"] = conf["avatar"]
                                
                    # Refresh session with new settings
                    if room.session:
                        room.session.group_name = room.group_name
                        room.session.member_configs = room.member_configs
                    
                    # Save config after update
                    room.save_config()

                    # Broadcast update to all clients
                    await room.broadcast({
                        "type": "settings_updated",
                        "group_name": room.group_name,
                        "member_configs": room.member_configs
                    })

                elif data["type"] == "user_typing":
                    # Update user typing status in the session
                    if room.session:
                        room.session.is_user_typing = data.get("is_typing", False)

                elif data["type"] == "start":
                    # 启动对话循环
                    room.start_chat()
                
                elif data["type"] == "stop":
                    # 停止对话循环
                    # 如果是剧本模式，且不是手动暂停而是“结束事件”，我们需要判断意图。
                    # 根据需求："User can also manually click stop simulation to end this conversation, forcing this event to end, entering the next event."
                    # 所以只要点击停止，且在剧本模式下，就视为强制推进。
                    if room.session and room.scenario_config.get("enabled"):
                         await room.session.force_advance_scenario(room.history)
                         # Broadcast update so frontend sees new active box
                         await room.broadcast({
                            "type": "scenario_status", 
                            "current_event_idx": room.session.current_event_idx,
                            "events": room.scenario_config.get("events", [])
                         })
                    
                    await room.stop_chat()
                
                elif data["type"] == "clear":
                    # 清空历史
                    room.history = []
                    await room.broadcast({"type": "history", "messages": []})
                
                elif data["type"] == "reset":
                    # 停止并清空
                    await room.stop_chat()
                    room.history = []
                    await room.broadcast({"type": "history", "messages": []})
                
                elif data["type"] == "get_members":
                    # 获取当前成员列表
                    members = [{"name": "Gaia", "is_user": True, "is_manager": True}] # User is always manager-like
                    for p in room.probes:
                        m_name = p._modelName
                        config = room.member_configs.get(m_name, {})
                        members.append({
                            "name": m_name, 
                            "nickname": config.get("nickname", m_name), # Add nickname
                            "is_user": False,
                            "is_manager": config.get("is_manager", False),
                            "custom_prompt": config.get("custom_prompt", ""),
                            "avatar": config.get("avatar", "")
                        })
                    
                    await websocket.send_json({
                        "type": "members",
                        "members": members,
                        "group_name": room.group_name
                    })
                
                elif data["type"] == "get_history":
                    # 获取历史记录
                    await websocket.send_json({
                        "type": "history",
                        "messages": room.history
                    })
            except Exception as e:
                print(f"Error processing message: {e}")
                await websocket.send_json({"type": "system", "content": f"处理请求时出错: {str(e)}"})
                
    except WebSocketDisconnect:
        room.disconnect(websocket)
    except Exception as e:
        print(f"WS Endpoint Error: {e}")
        room.disconnect(websocket)


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Group Chat WebSocket Server"}


@app.get("/rooms")
async def list_rooms():
    return {
        "rooms": [
            {
                "id": room_id,
                "clients": len(room.clients),
                "is_running": room.is_running,
                "message_count": len(room.history)
            }
            for room_id, room in rooms.items()
        ]
    }

# --- God Mode Control Endpoints ---

class ControlRequest(BaseModel):
    content: Optional[str] = None
    event_idx: Optional[int] = None
    scenario_events: Optional[List[dict]] = None
    group_name: Optional[str] = None

@app.post("/control/{room_id}/group_name")
async def set_group_name(room_id: str, request: ControlRequest):
    """设置群名称"""
    room = get_or_create_room(room_id)
    if request.group_name:
        room.update_group_name(request.group_name)
    return {"status": "success", "group_name": room.group_name}

@app.post("/control/{room_id}/pause")
async def pause_room(room_id: str):
    room = rooms.get(room_id)
    if room:
        room.set_paused(True)
        return {"status": "paused"}
    return {"error": "Room not found"}

@app.post("/control/{room_id}/resume")
async def resume_room(room_id: str):
    room = rooms.get(room_id)
    if room:
        room.set_paused(False)
        return {"status": "resumed"}
    return {"error": "Room not found"}

@app.post("/control/{room_id}/event")
async def inject_event(room_id: str, req: ControlRequest):
    room = rooms.get(room_id)
    if room and req.content:
        await room.inject_event(req.content)
        return {"status": "event_injected"}
    return {"error": "Room not found or empty content"}

@app.post("/control/{room_id}/jump")
async def jump_event(room_id: str, req: ControlRequest):
    room = rooms.get(room_id)
    if room and req.event_idx is not None:
        room.jump_to_event(req.event_idx)
        return {"status": "jumped"}
    return {"error": "Room not found or invalid index"}

@app.post("/control/{room_id}/update_scenario")
async def update_scenario_endpoint(room_id: str, req: ControlRequest):
    room = rooms.get(room_id)
    if room and req.scenario_events is not None:
        room.update_scenario(req.scenario_events)
        return {"status": "scenario_updated"}
    return {"error": "Room not found or invalid events"}

@app.get("/control/{room_id}/history")
async def get_history(room_id: str):
    room = rooms.get(room_id)
    if room:
        return {
            "history": room.history, 
            "current_event_idx": room.session.current_event_idx if room.session else 0,
            "scenario": room.scenario_config.get("events", [])
        }
    return {"history": [], "scenario": []}

@app.get("/control/{room_id}/status")
async def get_status(room_id: str):
    room = rooms.get(room_id)
    if room:
        return {
            "is_running": room.is_running,
            "is_paused": room.session.is_paused if room.session else False,
            "current_event_idx": room.session.current_event_idx if room.session else 0,
            "total_events": len(room.scenario_config.get("events", []))
        }
    return {"is_running": False, "is_paused": False}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
