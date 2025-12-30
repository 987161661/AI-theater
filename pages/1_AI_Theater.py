import streamlit as st
import pandas as pd
import requests
import time
import json
from core.state.manager import state_manager
from core.llm_provider import LLMProvider
from components.director_panel import render_director_panel
from components.world_bible_panel import render_world_bible_panel
from core.director import Director

# --- Initialization ---
state_manager.initialize()

st.set_page_config(page_title="AI Theater", page_icon="🎭", layout="wide")
st.title("🎭 AI Theater (Modular)")

# --- Global Config Check ---
if not state_manager.llm_configs:
    st.warning("请先在 Config 页面配置 API Key！")
    st.stop()

def get_client(config_name: str):
    config = next((c for c in state_manager.llm_configs if c["name"] == config_name), None)
    if config:
        return LLMProvider(config["api_key"], config["base_url"], config["model"]).client, config["model"]
    return None, None

# --- Layout ---
tab_director, tab_casting, tab_stage = st.tabs([
    "🎬 AI 导演 (Director)", 
    "🎭 角色分配 (Casting)", 
    "🏟️ 舞台表演 (Stage)"
])

# Selection shared across panels
selected_model_name = st.sidebar.selectbox(
    "当前操作模型 (LLM Brain)", 
    [c["name"] for c in state_manager.llm_configs]
)
client, model = get_client(selected_model_name)

# ==========================================
# TAB 1: AI DIRECTOR
# ==========================================
with tab_director:
    render_director_panel(client, model)

# ==========================================
# TAB 2: CASTING
# ==========================================
with tab_casting:
    render_world_bible_panel(client, model)
    st.divider()
    st.subheader("Phase 2: 角色入驻 (Coming Soon)")
    st.info("正在将自动选角与 Persona Factory 组件化...")

# ==========================================
# TAB 3: STAGE
# ==========================================
with tab_stage:
    st.header("🏟️ 实时大剧场 (Stage Hub)")
    
    # 0. Helper: Fetch Status from Stage Server (God Mode Backend)
    SERVER_URL = "http://localhost:8001"
    try:
        status_res = requests.get(f"{SERVER_URL}/status", timeout=1.0)
        status_data = status_res.json()
        is_playing = status_data.get("is_playing", False)
        current_idx = status_data.get("current_index", 0)
        total_events = status_data.get("total_events", 0)
    except:
        status_data = {}
        is_playing = False
        current_idx = 0
        total_events = 0
        # st.caption("⚠️ 无法连接到导演控制服务器 (Stage Server)")

    # 1.上帝控制器 (God Controller)
    with st.container(border=True):
        st.subheader("🕹️ 上帝控制器 (God Mode)")
        
        c_ctl1, c_ctl2, c_ctl3 = st.columns([1, 4, 1])
        
        with c_ctl1:
            if is_playing:
                if st.button("⏸️ 暂停", use_container_width=True, help="暂停当前表演"):
                    requests.post(f"{SERVER_URL}/control?action=pause")
                    st.rerun()
            else:
                btn_label = "▶️ 开始" if current_idx == 0 else "▶️ 继续"
                if st.button(btn_label, type="primary", use_container_width=True, help="启动或恢复表演"):
                    requests.post(f"{SERVER_URL}/control?action={'start' if current_idx == 0 else 'resume'}")
                    st.rerun()
        
        with c_ctl2:
            if total_events > 0:
                target_idx = st.slider(
                    "⏳ 时间轴 (Timeline)", 
                    0, max(0, total_events - 1), current_idx, 
                    format="Event %d",
                    help="拖动以跳转到不同的剧情节点"
                )
            else:
                st.caption("⏳ 时间轴已就绪 (等待剧本初始化推送)")
                target_idx = 0
        
        with c_ctl3:
            if st.button("⏩ 跳转", use_container_width=True, help="强制跳转到选定时间点"):
                requests.post(f"{SERVER_URL}/control?action=jump&value={target_idx}")
                st.rerun()

        # 2. Sudden Event Injection
        with st.expander("⚡ 突发事件注入 (Event Injection)", expanded=False):
            c_inj1, c_inj2 = st.columns([4, 1])
            with c_inj1:
                event_inj_text = st.text_input("事件内容", placeholder="例如：突然亮起红灯，警报大作...", key="event_inj_input", label_visibility="collapsed")
            with c_inj2:
                if st.button("注入", use_container_width=True, type="primary"):
                    if event_inj_text:
                        requests.post(f"{SERVER_URL}/control?action=inject&content={event_inj_text}")
                        st.success("事件已注入舞台")
                        time.sleep(0.5)
                        st.rerun()

        # 3. AI Director Chat
        with st.expander("🎬 AI 导演会话 (Director Consult)", expanded=False):
            st.caption("您可以直接与导演对话，要求其调整后续剧本或改变演出风格。")
            
            if "director_chat_msgs" not in st.session_state:
                st.session_state.director_chat_msgs = []
            
            # Show chat history
            for msg in st.session_state.director_chat_msgs:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            # Input
            dir_input = st.text_area("向导演下达指令...", placeholder="比如：节奏太快了，让他们多吵一会儿；或者：给主角增加一个秘密身份...", height=80, key="dir_consult_input")
            
            if st.button("发送指令", use_container_width=True):
                if dir_input:
                    # Add user message
                    st.session_state.director_chat_msgs.append({"role": "user", "content": dir_input})
                    
                    # Call Director Logic
                    director = Director(client, model)
                    with st.spinner("导演正在审视当前剧本逻辑..."):
                        # Get current script from session state
                        current_script = st.session_state.scenario_df.to_dict("records") if not st.session_state.scenario_df.empty else []
                        
                        # Consult
                        consult_res = director.consult(st.session_state.director_chat_msgs, current_script)
                        
                        # Add reply
                        reply = consult_res["reply"]
                        st.session_state.director_chat_msgs.append({"role": "assistant", "content": reply})
                        
                        # Handle hot patch action
                        action = consult_res["action"]
                        if action and action.get("type") == "update_script":
                            new_events = action.get("new_events", [])
                            if new_events:
                                requests.post(f"{SERVER_URL}/update_scenario", json=new_events)
                                st.success("🚀 剧本已根据导演建议实时更新！")
                                
                                # Sync back to session state if needed (optional)
                                # new_df = pd.DataFrame(new_events)
                                # st.session_state.scenario_df = ...
                    
                    st.rerun()

    # WebSocket Chat Component
    st.divider()
    from components.websocket_chat import render_websocket_chat
    
    # Prepare configs for backend
    model_configs = []
    for config in state_manager.llm_configs:
        mid = config["name"]
        model_configs.append({
            "model_name": mid,
            "nickname": st.session_state.nicknames.get(mid, mid),
            "api_key": config["api_key"],
            "base_url": config["base_url"],
            "custom_prompt": st.session_state.custom_prompts.get(mid, ""),
            "memory": st.session_state.custom_memories.get(mid, "")
        })

    scenario_config = {
        "enabled": not st.session_state.scenario_df.empty,
        "events": st.session_state.scenario_df.to_dict("records") if not st.session_state.scenario_df.empty else [],
        "stage_type": st.session_state.current_stage_type
    }

    render_websocket_chat(
        room_id="ai_theater_main",
        ws_url="ws://localhost:8001",
        member_count=len(model_configs) + 1,
        model_configs=model_configs,
        scenario_config=scenario_config
    )
