import streamlit as st
import pandas as pd
import requests
import time
import json

# --- Initialization (Must be first) ---
st.set_page_config(page_title="AI Theater", page_icon="🎭", layout="wide")

from core.state.manager import state_manager
from core.llm_provider import LLMProvider
from components.director_panel import render_director_panel, handle_theme_generation
from components.world_bible_panel import render_world_bible_panel
from components.websocket_chat import render_websocket_chat
from core.director import Director
from core.utils.server_manager import ensure_backend_running

state_manager.initialize()

# --- Auto-start Backend Check ---
ensure_backend_running()

# --- Global Config Check ---
if not state_manager.llm_configs:
    st.title("🎭 AI Theater")
    st.warning("请先在 Config 页面配置 API Key！")
    st.stop()

# --- Navigation & Programmatic Switching ---
if "active_theater_tab" not in st.session_state:
    st.session_state.active_theater_tab = "🎬 AI 导演"

# Handle programmatic navigation (from director_panel)
if st.session_state.get("nav_to_casting"):
    st.session_state.active_theater_tab = "🎭 角色分配"
    del st.session_state["nav_to_casting"]

# --- Sidebar Model Selection Logic ---
available_models = []
for config in state_manager.llm_configs:
    provider_name = config["name"]
    models = config.get("fetched_models", [])
    if not models:
        models = [config.get("model", "default")]
    
    for m in models:
        available_models.append({
            "label": f"[{provider_name}] {m}",
            "config": config,
            "model_id": m
        })

if not available_models:
    st.title("🎭 AI Theater")
    st.error("没有可用模型，请前往配置页面。")
    st.stop()

with st.sidebar:
    st.subheader("⚙️ 全局配置")
    selected_model_option = st.selectbox(
        "🧠 操作大脑 (LLM Brain)", 
        options=available_models,
        format_func=lambda x: x["label"]
    )
    
    st.divider()
    st.subheader("🧭 导航菜单")
    # Replace st.tabs with a controllable radio button
    menu_options = ["🎬 AI 导演", "🎭 角色分配", "🏟️ 舞台表演"]
    selection = st.radio(
        "前往模块",
        options=menu_options,
        index=menu_options.index(st.session_state.active_theater_tab),
        key="nav_radio"
    )
    # Sync radio back to state
    st.session_state.active_theater_tab = selection

# --- Main Logic ---
st.title(f"{st.session_state.active_theater_tab}")

client = LLMProvider(
    selected_model_option["config"]["api_key"], 
    selected_model_option["config"]["base_url"], 
    selected_model_option["model_id"]
).client
model = selected_model_option["model_id"]

if st.session_state.active_theater_tab == "🎬 AI 导演":
    handle_theme_generation(client, model)
    render_director_panel(client, model)
elif st.session_state.active_theater_tab == "🎭 角色分配":
    render_world_bible_panel(client, model)
elif st.session_state.active_theater_tab == "🏟️ 舞台表演":
    if st.session_state.scenario_df.empty:
        st.warning("⚠️ 请先在【AI 导演】生成剧本")
        st.stop()
        
    if not st.session_state.get("actor_personas"):
         st.warning("⚠️ 请先在【角色分配】完成选角和人设生成")
         st.stop()

    # 1. Prepare Backend Init Data
    api_url = "http://localhost:8000"
    
    # Actors Config
    actors_payload = []
    # Convert from new 'actor_personas' dict structure
    for aid, p_data in st.session_state.actor_personas.items():
        if p_data.get("source_type") == "AI":
            # Find the config for this model
            raw_model_id = p_data.get("model_id", "")
            
            # Parse "ModelName (ProviderName)" format
            import re
            match = re.match(r"(.*) \((.*)\)", raw_model_id)
            
            matching_cfg = None
            specific_model = None
            
            if match:
                specific_model = match.group(1)
                provider_name = match.group(2)
                # Find provider by name
                matching_cfg = next((c for c in state_manager.llm_configs if c.get("name") == provider_name), None)
            else:
                # Fallback to legacy behavior (exact match or default)
                specific_model = raw_model_id
                matching_cfg = next((c for c in state_manager.llm_configs if c.get("name") == raw_model_id or c.get("model") == raw_model_id), None)

            # If not found by exact name, try to use the first available or the one selected in current session
            if not matching_cfg and state_manager.llm_configs:
                 matching_cfg = state_manager.llm_configs[0]

            if matching_cfg:
                # Create a copy to avoid mutating global state, and set the specific model
                # This ensures the backend uses the exact model selected for this actor
                cfg_copy = matching_cfg.copy()
                if specific_model:
                    cfg_copy["model"] = specific_model

                # Use Nickname as the primary ID for the backend if possible, or keep role name but ensure display is correct.
                # User wants "AI actor's group nickname to be configured".
                # If we use nickname here, the backend knows them by nickname.
                actor_id = p_data.get("nickname") or p_data.get("role_name") or aid
                actors_payload.append({
                    "name": actor_id, 
                    "llm_config": cfg_copy, # Pass specific config with correct model
                    "system_prompt": p_data.get("system_prompt", ""),
                    "memory": "\n".join(p_data.get("initial_memories", [])) if isinstance(p_data.get("initial_memories"), list) else p_data.get("initial_memories", "")
                })

    # Script Config
    raw_script = st.session_state.scenario_df.to_dict("records")
    script_payload = []
    for item in raw_script:
        # Map frontend DataFrame columns (Title Case) to Backend Pydantic Model (snake_case)
        # ScriptEvent(timeline, event, characters, description, location, goal)
        event_content = item.get("Event", "")
        # Use first sentence or first 30 chars as title if event is long
        event_title = event_content.split("。")[0][:30] if event_content else "New Event"
        
        script_payload.append({
            "timeline": item.get("Time", "Unknown Time"),
            "event": event_title,
            "description": event_content,
            "characters": item.get("Characters", ""),
            "location": item.get("Location", "默认地点"),
            "goal": item.get("Goal", "")
        })
    
    # World Bible
    bible_payload = st.session_state.world_bible

    # Stage Type
    stage_type = st.session_state.get("current_stage_type", "聊天群聊")

    # 2. Auto-Initialize Backend on first entry to stage
    # Key to track if we've initialized in this session
    init_key = "stage_backend_initialized"
    if not st.session_state.get(init_key) and actors_payload:
        try:
            init_payload = {
                "script": script_payload,
                "actors": actors_payload,
                "world_bible": bible_payload,
                "stage_type": stage_type
            }
            resp = requests.post(f"{api_url}/init", json=init_payload, timeout=5)
            if resp.status_code == 200:
                st.session_state[init_key] = True
                st.toast("✅ 舞台已自动初始化！")
            else:
                # Show detailed error info
                st.error(f"初始化失败 (HTTP {resp.status_code})")
                with st.expander("🔍 错误详情", expanded=True):
                    st.code(resp.text, language="json")
                    st.caption(f"Request URL: {api_url}/init")
                    st.caption(f"Actors: {len(actors_payload)}, Script Events: {len(script_payload)}")
        except requests.exceptions.ConnectionError as e:
            st.error(f"🔴 后台连接失败 (chat_server.py 未运行或端口错误)")
            st.caption(f"URL: {api_url}/init | Error: {e}")
        except Exception as e:
            st.error(f"初始化异常: {type(e).__name__}: {e}")
    
    # Manual control button
    col_ctrl1, col_ctrl2 = st.columns([1, 5])
    with col_ctrl1:
        if st.button("🚀 重新初始化舞台", type="secondary"):
            st.session_state[init_key] = False  # Force re-init
            try:
                resp = requests.post(f"{api_url}/init", json={
                    "script": script_payload,
                    "actors": actors_payload,
                    "world_bible": bible_payload,
                    "stage_type": stage_type
                })
                if resp.status_code == 200:
                    st.session_state[init_key] = True
                    st.toast("✅ 后台重新初始化成功！")
                else:
                    st.error(f"初始化失败: {resp.text}")
            except Exception as e:
                st.error(f"连接后台失败: {e}")

    # 3. Render WebSocket Chat
    # Construct model configs for frontend display
    frontend_model_configs = []
    for aid, p_data in st.session_state.actor_personas.items():
         if p_data.get("source_type") == "AI":
             frontend_model_configs.append({
                 "model_name": p_data.get("nickname") or p_data.get("role_name"),
                 "avatar": "🤖"
             })
    
    st.divider()
    render_websocket_chat(
        room_id="ai_theater_live",
        ws_url="ws://localhost:8000",
        member_count=len(actors_payload) + 1, # +1 for user
        model_configs=frontend_model_configs,
        scenario_config={
            "enabled": True,
            "events": script_payload,
            "stage_type": stage_type
        },
        group_name=bible_payload.get("group_name", "AI Theater"),
        is_stage_view=True
    )

    # --- God Mode Controller ---
    st.divider()
    st.subheader("🌩️ 上帝操控台 (God Mode)")

    # Initialize session state for pause
    if "god_mode_paused" not in st.session_state:
        st.session_state.god_mode_paused = False

    col_gm1, col_gm2 = st.columns([1, 4])
    with col_gm1:
        # Pause/Resume Toggle
        is_paused = st.session_state.god_mode_paused
        if is_paused:
            if st.button("▶️ 恢复 (Resume)", type="primary", use_container_width=True):
                try:
                    requests.post(f"{api_url}/control", params={"action": "resume"})
                    st.session_state.god_mode_paused = False
                    st.rerun()
                except Exception as e:
                    st.error(f"连接失败: {e}")
        else:
            if st.button("⏸️ 暂停 (Pause)", type="secondary", use_container_width=True):
                try:
                    requests.post(f"{api_url}/control", params={"action": "pause"})
                    st.session_state.god_mode_paused = True
                    st.rerun()
                except Exception as e:
                    st.error(f"连接失败: {e}")

    if is_paused:
        st.info("⏸️ 舞台已冻结。现在可以进行上帝干预。")
        
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.markdown("### ⚡ 突发事件 (Sudden Events)")
            st.caption("在下方输入框中填写事件，点击⚡按钮发送给对应角色。")
            
            # 1. Global Event
            with st.expander("🌍 全局事件 (发送给所有人)", expanded=True):
                c1, c2 = st.columns([4, 1])
                global_evt = c1.text_input("全局事件描述", key="god_global_input", label_visibility="collapsed", placeholder="例如：忽然地震了")
                if c2.button("⚡ 发送", key="god_global_btn"):
                    if global_evt:
                        try:
                            requests.post(f"{api_url}/god_mode/inject", json={"content": global_evt})
                            st.toast("⚡ 全局神谕已降临！")
                        except Exception as e:
                            st.error(f"失败: {e}")

            # 2. Per Actor Events
            st.markdown("#### 👤 角色专属事件")
            for actor in actors_payload:
                a_name = actor["name"]
                c1, c2, c3 = st.columns([1, 3, 1])
                c1.markdown(f"**{a_name}**")
                val = c2.text_input(f"input_{a_name}", key=f"god_input_{a_name}", label_visibility="collapsed", placeholder=f"给 {a_name} 的突发状况...")
                if c3.button("⚡", key=f"god_btn_{a_name}"):
                    if val:
                        try:
                            requests.post(f"{api_url}/god_mode/inject", json={"actor_name": a_name, "content": val})
                            st.toast(f"⚡ 神谕已发送给 {a_name}！")
                        except Exception as e:
                            st.error(f"失败: {e}")

        with col_right:
            st.markdown("### ⏳ 时空穿梭")
            st.caption("调整时间滑块（0-24小时）")
            
            # Fetch current status to get context if needed, but for now just a slider
            time_val = st.slider("时间 (小时)", 0, 23, 12, format="%d:00")
            
            # Optional: Allow minute adjustment
            # minute_val = st.slider("分钟", 0, 59, 0)
            
            if st.button("⏳ 确认穿越"):
                new_time = f"{time_val:02d}:00"
                try:
                    requests.post(f"{api_url}/god_mode/time_travel", json={"new_time": new_time})
                    st.toast(f"⏳ 时间已变更为 {new_time}")
                except Exception as e:
                    st.error(f"失败: {e}")
            
            st.info("⚠️ 注意：除非是超现实剧本，否则请勿将时间倒流到当前时间点之前。")

    else:
        st.caption("⏸️ 点击暂停按钮以启用上帝干预功能（突发事件、时空穿梭）。")
