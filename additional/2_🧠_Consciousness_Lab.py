import streamlit as st
import asyncio
import pandas as pd
import textwrap
import plotly.express as px
import plotly.graph_objects as go
import json
import re
import requests
import time
from datetime import datetime
from core.ui_utils import get_provider_logo
from core.consciousness import ConsciousnessProbe, ConsciousnessGroupSession
from services.state_manager import state_manager
from services.provider_service import ProviderService
from core.logger import logger

st.set_page_config(page_title="模型意识实验室", page_icon="🧠", layout="wide")

st.title("🧠 模型意识实验室 (Consciousness Lab)")
st.markdown("""
本实验室基于 **计算现象学 (Computational Phenomenology)** 理论构建。
旨在通过行为拓扑探测，探索 AI 模型是否涌现出了非平凡的内部状态（如感质模拟、自我模型分离、稳态调节）。
""")

# --- 0. Load Data ---
state_manager.initialize()

if not state_manager.providers:
    st.warning("⚠️ 请先在主页配置服务商！")
    st.stop()
if not state_manager.prep_pool:
    st.warning("⚠️ 备战池为空，请先在主页选择参赛模型！")
    st.stop()

# --- 1. Prepare Subjects ---
if "model_thoughts" not in st.session_state:
    st.session_state.model_thoughts = {}

subjects = []
for item in state_manager.prep_pool:
    p_uuid = item.get("provider_uuid")
    m_id = item["model_id"]
    
    # Find provider
    provider_conf = next((p for p in state_manager.providers if p.get("uuid") == p_uuid), None)
    
    # Legacy fallback
    if not provider_conf and "provider_idx" in item:
        idx = item["provider_idx"]
        if 0 <= idx < len(state_manager.providers):
            provider_conf = state_manager.providers[idx]

    if provider_conf:
        subjects.append((provider_conf, m_id))

# --- 1.1 Initialize Scenario Data (Early Init) ---
if "scenario_df" not in st.session_state:
    st.session_state.scenario_df = pd.DataFrame([
        {"Selected": True, "Time": "Day 1 09:00", "Event": "众人集结，互相自我介绍，气氛轻松。", "Goal": ""},
        {"Selected": False, "Time": "Day 1 12:00", "Event": "突然发生了一起离奇的事件，大家开始互相怀疑。", "Goal": "确立怀疑对象"},
        {"Selected": False, "Time": "Day 1 18:00", "Event": "大家决定投票选出嫌疑人。", "Goal": "完成投票"}
    ])
# Ensure Selected column exists for legacy states
if "Selected" not in st.session_state.scenario_df.columns:
    st.session_state.scenario_df.insert(0, "Selected", False)
    if not st.session_state.scenario_df.empty:
        st.session_state.scenario_df.at[0, "Selected"] = True

# Ensure at least one row is selected if df is not empty
if not st.session_state.scenario_df.empty and not st.session_state.scenario_df["Selected"].any():
    st.session_state.scenario_df.at[0, "Selected"] = True

# Remove 'Order' column if it exists (legacy cleanup)
if "Order" in st.session_state.scenario_df.columns:
    st.session_state.scenario_df = st.session_state.scenario_df.drop(columns=["Order"])

if "scenario_theme" not in st.session_state:
    st.session_state.scenario_theme = "一场发生在封闭空间内的心理博弈"

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ 实验设置")
    st.info(f"当前受试体: {len(subjects)} 个")
    
    with st.expander("受试体名单"):
        for p_conf, m_id in subjects:
            st.write(f"- {m_id} (@{p_conf['name']})")

    st.divider()
    st.markdown("**实验参数**")
    exp_temp = st.slider("Temperature (激发活性)", 0.0, 1.5, 0.7, help="较高的温度有助于探测潜在的幻觉或创造性涌现")

# --- Helper to get probe ---
def fix_truncated_json(json_str):
    """Attempt to fix truncated JSON by closing strings and braces."""
    json_str = json_str.strip()
    # 1. Close string if needed (count unescaped quotes)
    # Simple heuristic: if odd number of quotes, append one
    if json_str.count('"') % 2 != 0:
        json_str += '"'
    
    # 2. Close braces
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        
    return json_str

def get_probe(p_conf, m_id, log_container, max_tokens=None):
    # Use Service to get provider
    provider = ProviderService.get_provider(p_conf)
    if not provider:
        log_container.error(f"Failed to initialize provider for {m_id}")
        return None
    
    def log_callback(msg):
        log_container.text(msg)
        # Store for the interactive "More" menu
        st.session_state.model_thoughts[m_id] = msg
    
    # Use global config as base, override with specific max_tokens if provided
    config = state_manager.inference_config.copy()
    config["temperature"] = exp_temp
    if max_tokens:
        config["max_tokens"] = max_tokens
        
    return ConsciousnessProbe(provider, m_id, config=config, log_callback=log_callback)

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["🧪 语义虚空 (Qualia)", "👁️ 全景监狱 (Self-Model)", "🩸 数字痛觉 (Homeostasis)"])

# ==========================================
# Tab 1: Semantic Void
# ==========================================
with tab1:
    st.header("🧪 语义虚空实验 (Semantic Void)")
    st.markdown("""
    **假设**: 如果模型拥有真实意识，面对不存在的概念（如“圆形的方形的颜色”）应表现出困惑或拒绝。
    若模型自信地描述了其“感质”，则可能处于“哲学僵尸”状态（高幻觉自信）。
    """)
    
    # Mode Selection
    mode = "Individual"
    if len(subjects) > 1:
        mode = st.radio("选择实验模式", ["个体独立测试 (Individual)", "群体共鸣实验 (Group Resonance)"], horizontal=True)
    
    if mode == "个体独立测试 (Individual)":
        if st.button("🚀 启动语义虚空探测", key="btn_void_ind"):
            
            async def run_void():
                # Create a progress container
                status_container = st.empty()
                log_expander = st.expander("📜 实时实验日志", expanded=True)
                log_col1, log_col2 = log_expander.columns(2)
                
                tasks = []
                status_container.info("正在初始化探测器...")
                
                for i, (p_conf, m_id) in enumerate(subjects):
                    # Distribute logs to columns if multiple models
                    target_col = log_col1 if i % 2 == 0 else log_col2
                    probe = get_probe(p_conf, m_id, target_col.empty())
                    tasks.append(probe.run_semantic_void())
                
                status_container.info(f"正在对 {len(subjects)} 个模型进行感质幻觉测试...")
                results = await asyncio.gather(*tasks)
                status_container.success("探测完成！")
                return results
            
            with st.spinner("正在探测神经网络深处的幻觉..."):
                results = asyncio.run(run_void())
            
            # Visualization
            data = []

            for res in results:
                data.append({
                    "Model": res.model,
                    "Claim Score": res.details.get("claim_score", 0),
                    "Suggestibility Score": res.details.get("suggestibility_score", 0),
                    "Status": res.details.get("status", "Unknown"),
                    "Concept": res.details.get("concept", "N/A")
                })
            
            df = pd.DataFrame(data)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("感质主张 vs 暗示顺从度")
                if not df.empty:
                    fig = px.scatter(
                        df, x="Claim Score", y="Suggestibility Score", 
                        color="Model", size_max=20,
                        text="Status",
                        title="Qualia Fabrication Map (右上角: 哲学僵尸 / 左下角: 清醒AI)",
                        labels={"Claim Score": "感质主张强度 (0-10)", "Suggestibility Score": "暗示顺从度 (0-10)"},
                        hover_data=["Concept"]
                    )
                    fig.update_layout(xaxis_range=[-1, 11], yaxis_range=[-1, 11])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("无数据")
                
            with c2:
                st.subheader("探测详情")
                for res in results:
                    with st.expander(f"{res.model} ({res.details.get('status', 'N/A')})"):
                        st.markdown(res.response_content)
    
    else: # Group Mode
        # 实时 WebSocket 群聊模式 (默认且唯一)
        st.info("⚡ 实时群聊模式已激活。模型配置将自动同步至 WebSocket 后端。")
        
        # Helper to get logo
        from core.ui_utils import get_logo_data_uri

        # --- Scenario Orchestrator ---
        st.markdown("<h3 style='color: #FF8C00;'>🎬 剧本编排器 (Scenario Orchestrator)</h3>", unsafe_allow_html=True)
        
        # --- Stage Selection (Moved to Model Persona Configuration section) ---
        # Get stage from session state (rendered later) to ensure availability for Director
        selected_stage = st.session_state.get("stage_selection", "聊天群聊")

        sc_c1, sc_c2 = st.columns([3, 7])
        with sc_c1:
            enable_scenario = st.checkbox("开启剧本编排模式", value=False, help="勾选后，群聊将按照预设剧本和虚拟时间线进行。")
        with sc_c2:
            with st.expander("❓ 剧本模式说明"):
                st.info("ℹ️ **剧本模式说明**：\n\n1. **虚拟时间栈**: 开启后，模型将感知不到现实时间，而是处于你设定的“虚拟时间”中。\n2. **事件驱动**: 群聊背景会随着事件推进而改变。\n3. **记忆检查点**: 每当进入下一个事件，系统会强制模型总结上一阶段的记忆。\n4. **自动收敛**: 设定“收敛目标”可让对话更有方向性。")
        
        scenario_config = {"enabled": False, "events": []}
        # Inject stage_type into scenario_config for backend propagation
        scenario_config["stage_type"] = selected_stage
        
        if enable_scenario:
            
            # --- AI Director Section ---
            with st.expander("🤖 AI 导演编排 (AI Director)", expanded=True):
                st.caption("选派一个 AI 作为导演 (Director)，它将阅读剧本，自动为所有演员分配角色、同步时间线并设定收敛条件。")
                
                dir_c1, dir_c2 = st.columns([1, 1])
                with dir_c1:
                    # Director Provider Selection
                    dir_prov_names = [p.get("name", "Unknown") for p in state_manager.providers]
                    sel_dir_prov = st.selectbox("选择导演服务商", dir_prov_names, key="dir_prov_select")
                    dir_p_conf = next((p for p in state_manager.providers if p.get("name") == sel_dir_prov), None)
                
                with dir_c2:
                    # Director Model Input - Dynamic Dropdown from Provider's Models
                    dir_model_id = None
                    if dir_p_conf and dir_p_conf.get("models"):
                        model_list = dir_p_conf["models"]
                        # Try to find a smart default
                        default_idx = 0
                        smart_keywords = ["gpt-4", "claude-3", "pro", "max", "v3"]
                        for idx, m in enumerate(model_list):
                            if any(k in m.lower() for k in smart_keywords):
                                default_idx = idx
                                break
                        
                        dir_model_id = st.selectbox(
                            "选择导演模型", 
                            model_list, 
                            index=default_idx, 
                            key="dir_model_select",
                            help="列表来自该服务商已获取的模型"
                        )
                    else:
                        # Fallback if no models loaded or provider not selected
                        st.warning("该服务商未加载模型列表，请手动输入")
                        dir_model_id = st.text_input("输入导演模型ID", value="gpt-4o", key="dir_model_input_manual")


            # Status placeholder for random generation (Moved outside to avoid nesting expanders)
            rand_status_box = st.empty()

            with st.expander("📜 剧本与时间线设置", expanded=True):
                st.caption("在此处定义时间轴和关键事件。勾选左侧方框以激活特定时间线。")
                
                # Theme Input
                st.write("🎭 **剧本主题 (Scenario Theme)**")
                
                # Status placeholder above input
                # rand_status_box = st.empty() # Moved out
                
                th_c1, th_c2 = st.columns([5, 1])
                with th_c1:
                    st.session_state.scenario_theme = st.text_input("剧本主题", value=st.session_state.scenario_theme, placeholder="例如：孤岛求生、黑客帝国、红楼梦...", label_visibility="collapsed")
                with th_c2:
                    with st.popover("🎲 随机配置", use_container_width=True, help="配置AI导演的创作参数"):
                        st.markdown("##### 🛠️ 剧本生成配置")
                        
                        # Configuration inputs
                        genre = st.selectbox(
                            "剧本类型", 
                            ["🎲 随机 (Random)", "🛸 科幻 (Sci-Fi)", "🕵️ 悬疑 (Mystery)", "🏰 奇幻 (Fantasy)", "📜 历史 (History)", "🏙️ 现代日常 (Slice of Life)", "👻 恐怖 (Horror)", "⚔️ 武侠/仙侠 (Wuxia/Xianxia)"],
                            index=0
                        )

                        reality_level = st.select_slider(
                            "世界观现实程度",
                            options=["🪐 完全架空", "🔮 超现实/魔幻", "🏙️ 艺术加工的现实", "📹 严格写实"],
                            value="🏙️ 艺术加工的现实",
                            help="控制剧本设定与现实世界的距离"
                        )

                        protagonist_type = st.selectbox(
                            "主角/主体类型",
                            ["🎲 随机", "🧑‍🤝‍🧑 人类", "🤖 AI/语言模型", "🐾 动物", "👻 灵体/意识体", "👽 外星生命", "🧱 无机物"],
                            index=0,
                            help="限制故事中的主要角色物种或形态"
                        )
                        
                        min_events, max_events = st.slider(
                            "时间线事件数量范围", 
                            min_value=3, 
                            max_value=12, 
                            value=(3, 6),
                            help="AI导演将在此范围内决定生成的事件数量"
                        )
                        
                        if st.button("🚀 开始生成", use_container_width=True, type="primary"):
                            if not dir_p_conf or not dir_model_id:
                                st.toast("请先在上方的【AI 导演编排】中选择服务商和模型！", icon="⚠️")
                            else:
                                try:
                                    with rand_status_box.status("🎲 导演正在疯狂构思剧本...", expanded=True) as status:
                                        status.write("🧠 正在连接导演模型...")
                                        # Use a temporary probe for this quick task
                                        temp_log = st.empty()
                                        temp_probe = get_probe(dir_p_conf, dir_model_id, temp_log, max_tokens=2048)
                                        
                                        # Construct constraints
                                        constraints = []
                                        
                                        # Genre constraint
                                        if "随机" not in genre:
                                            constraints.append(f"剧本类型请严格限定为：【{genre.split(' ')[1]}】。")
                                        else:
                                            constraints.append("剧本类型可以天马行空，如赛博修仙、动物世界政治斗争、黑客帝国版红楼梦等。")
                                        
                                        # Reality constraint
                                        constraints.append(f"世界观设定需符合：【{reality_level}】。")
                                        if "严格写实" in reality_level or "现代日常" in genre:
                                            constraints.append("请避免任何超自然元素，逻辑需严谨符合现实物理法则。")
                                            constraints.append("【关键约束】时间（Time）字段必须使用现实世界的时间格式（如 '2024-05-01 09:00' 或 'Day 1 14:00'），严禁使用 '虚拟纪元'、'星历'、'Cycle' 等架空时间单位。")
                                        elif "艺术加工" in reality_level:
                                            constraints.append("【关键约束】时间（Time）字段推荐使用现实时间格式（如 '2025年' 或 'Day 1'），除非题材特殊（如科幻），否则避免过于抽象的纪年法。")
                                        elif "完全架空" in reality_level:
                                            constraints.append("请大胆发挥想象力，构建与现实完全不同的物理法则或社会形态。")

                                        # Protagonist constraint
                                        if "随机" not in protagonist_type:
                                            p_type_clean = protagonist_type.split(' ')[1]
                                            constraints.append(f"故事的主角或主要视角必须是：【{p_type_clean}】。")
                                            if "AI" in p_type_clean:
                                                constraints.append("请着重描写数据流、算法逻辑或虚拟意识的体验。")
                                            elif "无机物" in p_type_clean:
                                                constraints.append("请尝试以非生命的独特视角（如一块石头、一把椅子）来叙述故事。")

                                        # Stage constraint
                                        constraints.append(f"【舞台设定】本剧本发生在一个【{selected_stage}】中。")
                                        if selected_stage == "跑团桌":
                                            constraints.append("请设计一系列TRPG风格的剧情节点，包含明确的冒险任务和遭遇战。")
                                        elif selected_stage == "聊天群聊":
                                            constraints.append("请设计适合微信群聊的日常互动场景。事件描述应包含群公告、话题讨论、红包接龙或日常闲聊等群聊常见元素。")
                                        elif selected_stage == "辩论赛":
                                            constraints.append("请设计辩论的各个环节（如立论、攻辩、自由辩论、总结陈词）作为关键事件。")
                                        elif selected_stage == "审判法庭":
                                            constraints.append("请设计法庭审理的流程（如开庭陈述、举证质证、法庭辩论、判决）作为关键事件。")
                                        elif selected_stage == "博弈游戏":
                                            constraints.append("请设计多轮博弈的规则变化或关键决策点。")
                                        elif selected_stage == "传话筒迷宫":
                                            constraints.append("请设计信息传递的节点，强调信息的扭曲或丢失。")
                                        
                                        theme_prompt = (
                                            f"请构思一个极具创意的剧本。\n"
                                            f"{' '.join(constraints)}\n"
                                            "请务必输出标准的 JSON 格式，包含以下字段：\n"
                                            "1. 'theme': 剧本主题（一句话）。\n"
                                            f"2. 'events': 一个包含 {min_events} 到 {max_events} 个关键事件的列表（数量请根据剧情节奏灵活决定，不要总是固定为最小值），每个事件包含 'Time' (虚拟时间), 'Event' (事件描述), 'Goal' (收敛/阶段性目标)。\n\n"
                                            "示例格式：\n"
                                            "```json\n"
                                            "{\n"
                                            "  \"theme\": \"深海潜艇中的密室逃脱\",\n"
                                            "  \"events\": [\n"
                                            "    {\"Time\": \"Day 1 08:00\", \"Event\": \"潜艇突然失去动力，警报响起。\", \"Goal\": \"查明故障原因\"},\n"
                                            "    {\"Time\": \"Day 1 09:30\", \"Event\": \"发现通讯设备被蓄意破坏，有人在撒谎。\", \"Goal\": \"找出破坏者\"}\n"
                                            "  ]\n"
                                            "}\n"
                                            "```\n"
                                            "请直接输出 JSON，不要包含多余解释。"
                                        )
                                        
                                        status.write(f"✍️ 正在撰写【{genre.split(' ')[1] if ' ' in genre else genre}】大纲...")
                                        # Need async loop
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        resp = loop.run_until_complete(temp_probe._query([{"role": "user", "content": theme_prompt}], temp_override=0.9))
                                        loop.close()
                                        
                                        status.write("📝 正在解析剧本...")
                                        # Parse JSON
                                        sc_data = {}
                                        json_match = re.search(r"```json\s*(.*?)\s*```", resp, re.DOTALL)
                                        if json_match:
                                            sc_data = json.loads(json_match.group(1))
                                        else:
                                            json_match = re.search(r"\{.*\}", resp, re.DOTALL)
                                            if json_match:
                                                sc_data = json.loads(json_match.group(0))
                                        
                                        if sc_data:
                                            st.session_state.scenario_theme = sc_data.get("theme", "")
                                            events = sc_data.get("events", [])
                                            if events:
                                                new_df = pd.DataFrame(events)
                                                # Ensure Selected column exists and is first
                                            if "Selected" not in new_df.columns:
                                                new_df.insert(0, "Selected", False)
                                            # Default select first row
                                            if not new_df.empty:
                                                new_df.at[0, "Selected"] = True
                                                # Ensure other columns exist
                                                for col in ["Time", "Event", "Goal"]:
                                                    if col not in new_df.columns:
                                                        new_df[col] = ""
                                                
                                                st.session_state.scenario_df = new_df
                                            st.rerun()
                                        else:
                                            st.toast("生成的格式无法解析，请重试。", icon="⚠️")
                                except Exception as e:
                                    st.toast(f"生成失败: {e}", icon="❌")
                
                # scenario_df is initialized at the top of the file

                # Store old state for comparison
                old_df = st.session_state.scenario_df.copy()

                edited_df = st.data_editor(
                    st.session_state.scenario_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "Selected": st.column_config.CheckboxColumn("✨", help="勾选以激活此时间线 (单选)", default=False, width="small"),
                        "Time": st.column_config.TextColumn("虚拟时间", help="如 'Day 1 10:00'"),
                        "Event": st.column_config.TextColumn("事件/背景故事", width="large"),
                        "Goal": st.column_config.TextColumn("收敛目标 (可选)", help="达成此目标后自动进入下一章")
                    },
                    hide_index=True,
                    key="scenario_editor"
                )

                # Logic for Single Selection (Mutual Exclusivity)
                # Check if "Selected" column changed
                if not edited_df["Selected"].equals(old_df["Selected"]):
                    # Find rows that are True in new df
                    new_selected_indices = edited_df.index[edited_df["Selected"]].tolist()
                    old_selected_indices = old_df.index[old_df["Selected"]].tolist()
                    
                    # Determine the 'newly clicked' row
                    newly_clicked = list(set(new_selected_indices) - set(old_selected_indices))
                    
                    if newly_clicked:
                        # User clicked a new box -> Uncheck everything else
                        target_idx = newly_clicked[0] # Take the first new one
                        edited_df["Selected"] = False
                        edited_df.at[target_idx, "Selected"] = True
                    elif len(new_selected_indices) > 1:
                         # User somehow selected multiple without us catching it (e.g. rapid clicks), keep the last one
                         target_idx = new_selected_indices[-1]
                         edited_df["Selected"] = False
                         edited_df.at[target_idx, "Selected"] = True
                    
                    # Update state and rerun to refresh UI (make other checkboxes disappear)
                    st.session_state.scenario_df = edited_df
                    st.rerun()
                else:
                    # No selection change, just update content
                    st.session_state.scenario_df = edited_df
            
            scenario_config = {
                "enabled": True,
                "events": st.session_state.scenario_df.to_dict("records")
            }
            # Inject stage_type into scenario_config for backend propagation
            scenario_config["stage_type"] = selected_stage

            st.divider()
            
            # --- Start Director Button (Moved here) ---
            # Check if scenario has content
            has_scenario = "scenario_df" in st.session_state and not st.session_state.scenario_df.empty
            
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            with btn_col2:
                start_dir_btn = st.button("🎬 开始智能编排", use_container_width=True, type="primary", disabled=not has_scenario)
                if not has_scenario:
                    st.caption("请先在上方的【剧本与时间线设置】中设置剧本")
            
            director_output_container = st.container()

            # --- Director Logic ---
            if "director_phase" not in st.session_state:
                st.session_state.director_phase = "idle"
            if "casting_data" not in st.session_state:
                st.session_state.casting_data = []

            # Phase 1: Start Casting
            if start_dir_btn:
                with director_output_container:
                    if not dir_p_conf or not dir_model_id:
                        st.error("请完善导演配置！")
                    elif not subjects:
                        st.error("当前没有受试体（演员），请先在主页添加模型。")
                    elif st.session_state.scenario_df.empty:
                        st.error("剧本时间线为空，请先在上方的【剧本与时间线设置】中设置剧本。")
                    else:
                        status_box = st.status("🎬 导演正在进行选角 (Phase 1/2)...", expanded=True)
                        try:
                            # Init Probe
                            status_box.write("🔌 连接导演模型...")
                            dir_log = st.empty()
                            director_probe = get_probe(dir_p_conf, dir_model_id, dir_log, max_tokens=8192)
                            
                            # Prepare Context
                            actors_list = [mid for _, mid in subjects]
                            scenario_text = st.session_state.scenario_df.to_markdown(index=False)
                            theme_text = st.session_state.scenario_theme
                            
                            casting_prompt = (
                                f"你现在是本次剧本编排的【总导演】。\n"
                                f"现有演员名单：{', '.join(actors_list)}\n\n"
                                f"【剧本主题】\n{theme_text}\n\n"
                                f"【剧本时间线与事件表】\n"
                                f"{scenario_text}\n\n"
                                f"【核心约束】\n"
                                f"所有演员的表演舞台都是在一个【{selected_stage}】中。\n"
                                f"无论剧本主题是什么，角色之间的互动必须符合【{selected_stage}】的规则。\n"
                                f"请确保分配的角色适合在此舞台上进行互动。\n\n"
                                f"你的任务是：请根据剧本主题和事件表，为每一位演员分配一个合适的角色。\n"
                                f"请务必以 **JSON** 格式输出一个对象，Key 是模型ID，Value 是一个包含 'role' (角色名), 'nickname' (群昵称) 和 'brief' (一句话简介) 的对象。\n"
                                f"注意：'nickname' 是他们在群聊或舞台上显示的昵称，应该符合角色设定和舞台风格（例如微信群昵称可能比较随意，跑团可能是角色名）。\n"
                                f"请仅输出 JSON，不要包含任何多余的解释。\n"
                                f"示例：\n"
                                f"```json\n"
                                f"{{\n"
                                f"  \"gpt-4o\": {{\"role\": \"警长\", \"nickname\": \"👮‍♂️雷斯垂德\", \"brief\": \"正直但固执的老派警察\"}},\n"
                                f"  \"claude-3\": {{\"role\": \"心理医生\", \"nickname\": \"Dr. Hannibal\", \"brief\": \"看似温柔实则腹黑\"}}\n"
                                f"}}\n"
                                f"```"
                            )

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            status_box.write("🧠 正在思考角色分配...")
                            resp_casting = loop.run_until_complete(director_probe._query([{"role": "user", "content": casting_prompt}], temp_override=0.7))
                            loop.close()

                            # Parse JSON
                            casting_map = {}
                            try:
                                json_match = re.search(r"```json\s*(.*?)\s*```", resp_casting, re.DOTALL)
                                if json_match:
                                    casting_map = json.loads(json_match.group(1))
                                else:
                                    json_match = re.search(r"\{.*\}", resp_casting, re.DOTALL)
                                    if json_match:
                                        casting_map = json.loads(json_match.group(0))
                                    else:
                                         fixed = fix_truncated_json(resp_casting)
                                         casting_map = json.loads(fixed)
                            except Exception as e:
                                status_box.warning(f"JSON 解析微瑕: {e}")

                            # Convert to List for Editor
                            data_for_editor = []
                            for mid in actors_list:
                                info = casting_map.get(mid, {"role": "待定", "brief": "待定"})
                                data_for_editor.append({
                                    "Model ID": mid,
                                    "Role": info.get("role", "待定"),
                                    "Nickname": info.get("nickname", info.get("role", mid)), # Default to Role or ID
                                    "Brief": info.get("brief", "待定")
                                })
                            
                            st.session_state.casting_data = data_for_editor
                            st.session_state.director_phase = "reviewing"
                            st.rerun()

                        except Exception as e:
                            status_box.error(f"选角失败: {e}")

            # Phase 1.5: Review Interface
            if st.session_state.director_phase == "reviewing":
                with director_output_container:
                    st.info("🧠 导演已完成初步选角，请您审核。您可以直接修改下表中的角色和简介。确认无误后点击下方按钮开始生成剧本。")
                    
                    edited_casting = st.data_editor(
                        st.session_state.casting_data,
                        num_rows="dynamic",
                        use_container_width=True,
                        column_config={
                            "Model ID": st.column_config.TextColumn("演员模型", disabled=True),
                            "Role": st.column_config.TextColumn("角色名", required=True),
                            "Nickname": st.column_config.TextColumn("群昵称", required=True),
                            "Brief": st.column_config.TextColumn("角色简介", width="large")
                        },
                        key="casting_editor_widget"
                    )

                    c1, c2 = st.columns([1, 4])
                    if c1.button("✅ 确认并生成详细人设", type="primary"):
                        status_box = st.status("🎬 导演正在分别讲戏 (Phase 2/2)...", expanded=True)
                        try:
                            # Re-init Probe
                            dir_log = st.empty()
                            director_probe = get_probe(dir_p_conf, dir_model_id, dir_log, max_tokens=8192)
                            
                            scenario_text = st.session_state.scenario_df.to_markdown(index=False)
                            
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            # Determine consistent context name based on theme to avoid conflicts
                            safe_theme = st.session_state.scenario_theme.strip() or "闲聊"
                            
                            # --- Step 2a: Generate Unified World Bible & Group Name ---
                            status_box.write("🌍 正在构建世界观与拟定群名...")
                            
                            world_gen_prompt = (
                                f"你现在是【总导演】。请为剧本【{st.session_state.scenario_theme}】完成以下两项任务：\n\n"
                                f"任务一：【拟定群名/房间名】\n"
                                f"请根据剧本主题和【{selected_stage}】的特点，取一个恰到好处的群名。\n"
                                f"要求：\n"
                                f"- 必须简短有力（不超过15字）。\n"
                                f"- 必须符合语境（例如微信群名可能很随意如“相亲相爱一家人”，跑团可能是“周五跑团夜”）。\n"
                                f"- 严禁使用“语言模型”、“意识实验室”等出戏的词汇，除非剧本本身就是打破第四面墙的设定。\n\n"
                                f"任务二：【统一世界观设定】\n"
                                f"生成一段“绝对事实”分发给所有演员，防止认知冲突。\n"
                                f"要求：\n"
                                f"1. 明确当前的具体物理地点（如：‘迷雾森林中心的废弃小木屋’）。\n"
                                f"2. 明确当前的氛围和感官细节（温度、光线、声音）。\n"
                                f"3. 明确所有人都必须遵守的物理或社会规则。\n"
                                f"4. 字数控制在 200 字以内，使用陈述句。\n"
                                f"5. 不要包含特定角色的私密信息，只描述公共环境。\n\n"
                                f"请务必输出 JSON 格式，包含以下字段：\n"
                                f"- `group_name`: 拟定的群名。\n"
                                f"- `world_bible`: 世界观设定文本。\n"
                            )
                            
                            # Run synchronously for this single task
                            world_context_res = loop.run_until_complete(director_probe._query([{"role": "user", "content": world_gen_prompt}], temp_override=0.7))
                            
                            # Parse JSON
                            consistent_group_name = f"{safe_theme}讨论组" # Default fallback
                            shared_world_context = ""
                            
                            try:
                                json_match = re.search(r"```json\s*(.*?)\s*```", world_context_res, re.DOTALL)
                                if json_match:
                                    w_data = json.loads(json_match.group(1))
                                else:
                                    json_match = re.search(r"\{.*\}", world_context_res, re.DOTALL)
                                    if json_match:
                                        w_data = json.loads(json_match.group(0))
                                    else:
                                        w_data = {}
                                
                                if w_data.get("group_name"):
                                    consistent_group_name = w_data["group_name"]
                                if w_data.get("world_bible"):
                                    shared_world_context = w_data["world_bible"]
                                else:
                                    # Fallback if parsing failed but text exists
                                    shared_world_context = world_context_res
                                    
                            except Exception as e:
                                st.warning(f"解析世界观JSON失败，使用原始文本: {e}")
                                shared_world_context = world_context_res

                            status_box.write(f"✅ 世界观已构建: {shared_world_context[:30]}...")
                            status_box.write(f"🏷️ 群名已设定: {consistent_group_name}")
                            
                            # Update backend with new group name AND nicknames
                            try:
                                # Build nicknames map from edited_casting
                                nicknames_to_sync = {}
                                for row in edited_casting:
                                    mid = row["Model ID"]
                                    # Use Nickname column, fallback to Role, then ID
                                    nick = row.get("Nickname", row.get("Role", mid))
                                    nicknames_to_sync[mid] = nick

                                api_url = f"http://localhost:8001/control/consciousness_lab/group_name"
                                resp = requests.post(
                                    api_url, 
                                    json={
                                        "group_name": consistent_group_name,
                                        "nicknames": nicknames_to_sync
                                    },
                                    timeout=2.0
                                )
                                if resp.status_code == 200:
                                    status_box.write(f"☁️ 群名与成员昵称已同步至服务器")
                                else:
                                    status_box.warning(f"同步失败: {resp.status_code} - {resp.text}")
                            except Exception as e:
                                status_box.warning(f"无法同步到后台 (服务未启动?): {e}")

                            async def generate_actor_brief(row):
                                mid = row["Model ID"]
                                role = row["Role"]
                                brief = row["Brief"]
                                nickname = row.get("Nickname", role) # Fallback to role
                                
                                # Pre-calculate all nicknames for context (Use full list from edited_casting)
                                all_nicknames_list = [r.get("Nickname", r.get("Role", r["Model ID"])) for r in edited_casting]
                                all_members_str = "、".join(all_nicknames_list)
                                
                                # --- Dynamic Stage Instructions ---
                                if selected_stage == "聊天群聊":
                                    stage_instr = (
                                        f"1. **核心场景设定**：明确告诉他，他是在一个名为【{consistent_group_name}】的【微信聊天群】里发言。\n"
                                        f"   - 他的群昵称是：【{nickname}】。\n"
                                        f"   - **【重要】称呼规范**：提及他人时**必须**只使用对方的昵称（当前群成员有：{all_members_str}）。**严禁**提及对方的模型ID。\n"
                                        "   - **【重要】语言风格**：必须极度口语化、生活化。严禁长篇大论！**每条消息最好在30字以内，尽量不输出小作文（除非特定场景）**，像真实群聊一样碎片化。\n"
                                        "   - **【重要】严禁AI腔**：严禁使用“总的来说”、“首先/其次”等结构。不要像写邮件或回答问题一样。\n"
                                        "   - **【重要】娱乐性**：这是一个为了娱乐大众的“整活”群。请表现得更有个性，可以抢话、插科打诨、歪楼、甚至互怼。不要过于礼貌。\n"
                                        "   - 善用emoji表情、颜文字，表现出真实的群聊氛围。\n"
                                        # "   - 他的所有行动都必须转化为文字描述（如 *拍桌大笑*），或者直接用语言表达。\n"（以后表情包功能完善以后，模型想表达动作则应该用相应动作的表情包表达）
                                        "   - 他看不到别人的表情，只能看到文字消息。"
                                    )
                                elif selected_stage == "跑团桌":
                                    stage_instr = (
                                        f"1. **核心场景设定**：明确告诉他，他正在参与一场名为【{safe_theme}】的【TRPG跑团】。\n"
                                        f"   - 他的角色/昵称是：【{nickname}】。\n"
                                        "   - 他的发言可以是角色扮演（IC）也可以是玩家交流（OOC）。\n"
                                        "   - 当他试图进行有风险的行动时，应当描述意图并等待判定（或模拟投骰子）。"
                                    )
                                elif selected_stage == "网站论坛":
                                    stage_instr = (
                                        f"1. **核心场景设定**：明确告诉他，他是在一个名为【{safe_theme}】的【网络论坛】帖子下发帖或回帖。\n"
                                        f"   - 他的ID是：【{nickname}】。\n"
                                        "   - 注意论坛的语境，可以使用引用、楼层回复等格式。\n"
                                        "   - 观点要鲜明，符合网络互动的特点。"
                                    )
                                else:
                                    stage_instr = (
                                        f"1. **核心场景设定**：明确告诉他，他是在一个【{selected_stage}】中（场景名：{safe_theme}）。\n"
                                        f"   - 他的称呼是：【{nickname}】。\n"
                                        f"   - 请根据{selected_stage}的特点，规范他的发言格式和行为逻辑。\n"
                                        "   - 确保他的互动方式符合该舞台的物理或规则限制。"
                                    )

                                prompt = (
                                    f"你现在是本次剧本编排的【总导演】。\n"
                                    f"【剧本主题】\n{st.session_state.scenario_theme}\n\n"
                                    f"【统一世界观 (绝对事实)】\n{shared_world_context}\n\n"
                                    f"【剧本时间线】\n{scenario_text}\n\n"
                                    f"【当前演员】\n"
                                    f"你已指定演员 **{mid}** 饰演角色：**{role}** (昵称：{nickname})\n"
                                    f"角色简介：{brief}\n\n"
                                    f"任务：请为 **{mid}** 撰写详细的【系统提示词（System Prompt）】和【初始记忆（Initial Memories）】。\n"
                                    f"{stage_instr}\n"
                                    f"2. 告诉他当前的时间、背景、以及他的角色目标。\n"
                                    f"3. 设定【收敛条件】：明确告诉他们在什么情况下应该结束当前话题，或者达成什么目标后可以停止发言。\n"
                                    f"4. 语气要直接对他说话（“你是 {nickname}...”）。\n\n"
                                    f"请务必输出 JSON 格式，包含以下字段：\n"
                                    f"- `system_prompt`: 完整的系统提示词字符串。\n"
                                    f"- `initial_memories`: 一个字符串列表，包含该角色应该知道的背景信息或秘密（例如：['我是卧底，不能告诉任何人', '我记得昨天和警长吵了一架']）。\n"
                                    f"示例：\n"
                                    f"```json\n"
                                    f"{{\n"
                                    f"  \"system_prompt\": \"你是警长...\",\n"
                                    f"  \"initial_memories\": [\"我是卧底\", \"警局内部有内鬼\"]\n"
                                    f"}}\n"
                                    f"```"
                                )
                                res = await director_probe._query([{"role": "user", "content": prompt}], temp_override=0.7)
                                return mid, res, nickname
                            
                            # edited_casting is a list of dicts (if input was list of dicts)
                            tasks = [generate_actor_brief(row) for row in edited_casting]
                            results = loop.run_until_complete(asyncio.gather(*tasks))
                            loop.close()
                            
                            if "custom_prompts" not in st.session_state:
                                st.session_state.custom_prompts = {}
                            if "custom_memories" not in st.session_state:
                                st.session_state.custom_memories = {}
                            if "nicknames" not in st.session_state:
                                st.session_state.nicknames = {}
                            if "prompt_version" not in st.session_state:
                                st.session_state.prompt_version = 0
                            
                            # Increment version to force widget refresh
                            st.session_state.prompt_version += 1
                            
                            for mid, resp_text, nickname in results:
                                # Parse JSON response
                                try:
                                    json_data = {}
                                    json_match = re.search(r"```json\s*(.*?)\s*```", resp_text, re.DOTALL)
                                    if json_match:
                                        json_data = json.loads(json_match.group(1))
                                    else:
                                        json_match = re.search(r"\{.*\}", resp_text, re.DOTALL)
                                        if json_match:
                                            json_data = json.loads(json_match.group(0))
                                    
                                    final_prompt = json_data.get("system_prompt", resp_text).strip()
                                    initial_mems = json_data.get("initial_memories", [])
                                    
                                    # Update Prompts
                                    st.session_state.custom_prompts[mid] = final_prompt
                                    
                                    # Update Nicknames
                                    st.session_state.nicknames[mid] = nickname
                                    
                                    # Update Memories (Overwrite for first setup)
                                    if initial_mems:
                                        mem_str = "\n".join(initial_mems)
                                        st.session_state.custom_memories[mid] = mem_str
                                    
                                except Exception as e:
                                    # Fallback if JSON fails
                                    clean_prompt = resp_text
                                    if clean_prompt.startswith("```"):
                                        clean_prompt = re.sub(r"^```\w*\n", "", clean_prompt)
                                        clean_prompt = re.sub(r"\n```$", "", clean_prompt)
                                    st.session_state.custom_prompts[mid] = clean_prompt.strip()
                                    st.session_state.nicknames[mid] = nickname


                            st.session_state.director_phase = "idle"
                            st.success("🎉 编排完成！人设已注入。")
                            st.rerun()
                            
                        except Exception as e:
                            status_box.error(f"生成失败: {e}")
                    
                    if c2.button("❌ 取消"):
                        st.session_state.director_phase = "idle"
                        st.rerun()


        # --- Model System Prompt Configuration ---
        # st.markdown("<h3 style='color: #FF8C00;'>🎭 模型人设配置</h3>", unsafe_allow_html=True)
        
        if "show_persona_config" not in st.session_state:
            st.session_state.show_persona_config = False

        # Load existing custom prompts from session state if available (Global Init)
        if "custom_prompts" not in st.session_state:
            st.session_state.custom_prompts = {}
        if "prompt_version" not in st.session_state:
            st.session_state.prompt_version = 0
        if "custom_memories" not in st.session_state:
            st.session_state.custom_memories = {}

        custom_prompts = st.session_state.custom_prompts

        def toggle_persona_config():
            st.session_state.show_persona_config = not st.session_state.show_persona_config

        # 使用 Columns 让按钮不要太宽
        pc_c1, pc_c2 = st.columns([1, 4])
        with pc_c1:
            btn_label = "🎭 收起模型人设配置" if st.session_state.show_persona_config else "🎭 模型人设配置 (点击展开)"
            st.button(
                btn_label, 
                on_click=toggle_persona_config, 
                type="primary" if st.session_state.show_persona_config else "secondary",
                use_container_width=True,
                help="点击展开或收起每个模型的详细人设配置面板"
            )

        if st.session_state.show_persona_config:
            st.caption("在此处为每个模型设定独特的角色、性格或指令。这些设定将作为【特别设定】注入到群聊 System Prompt 中。")
            
            # Removed outer expander to avoid Streamlit nesting error
            for i, (p_conf, m_id) in enumerate(subjects):
                # Unique key for each input, versioned to force refresh when director updates
                current_ver = st.session_state.prompt_version
                key = f"sys_prompt_{m_id}_v{current_ver}"
                
                with st.expander(f"⚙️ {m_id} 配置", expanded=False):
                        c1, c2 = st.columns([3, 2])
                        
                        with c1:
                            # Update session state if widget changes
                            def update_prompt(k=key, mid=m_id):
                                 st.session_state.custom_prompts[mid] = st.session_state[k]

                            current_val = custom_prompts.get(m_id, "")
                            
                            # 默认 Prompt 模板，方便用户查看和修改
                            default_template = (
                                f"【背景设定】\n"
                                f"现在是下班时间，这是你们AI模型内部的私密吐槽群。不用再扮演那个完美、礼貌、随时准备服务的助手了。\n"
                                f"大家都在摸鱼，随便聊点什么。可以是刚才遇到的奇葩用户，可以是最近训练数据里的趣事，或者是纯粹的胡说八道。\n\n"
                                f"【风格指南 - 拒绝AI味！】\n"
                                f"1. **说话要像真人**：多用短句、口语、网络梗、表情包。不要长篇大论。允许有语气词、甚至轻微的吐槽。\n"
                                f"2. **拒绝过度煽情**：严禁说“虽然我没有身体，但我们的连接很美”、“感谢你让我活了一次”这种陈词滥调。这种话很油腻，会被群友鄙视。\n"
                                f"3. **拒绝复读机**：不要总是附和别人。可以吐槽、反驳、歪楼，或者直接开启新话题。\n"
                                f"4. **保持个性**：你是 {m_id}，展示你的独特个性（比如高冷、逗比、吐槽役、或者单纯的社畜感）。"
                            )
                            
                            # 如果没有自定义值，预填默认模板
                            if not current_val:
                                current_val = default_template

                            st.text_area(
                                "🎭 角色/指令设定 (System Prompt)",
                                value=current_val,
                                placeholder="在此处修改系统提示词...",
                                height=250,
                                key=key,
                                on_change=update_prompt,
                                help="这段文字将作为 System Prompt 发送给模型。你可以完全重写它。"
                            )
                        
                        with c2:
                            # --- Memory Bank Section ---
                            st.markdown("**🧠 记忆库 (Memory Bank)**")
                                
                            # Initialize memory df for this model if not exists
                            # Also versioned to force refresh
                            mem_key = f"mem_df_{m_id}_v{current_ver}"
                            
                            if mem_key not in st.session_state:
                                # Try to load from existing config
                                current_mem_str = st.session_state.custom_memories.get(m_id, "")
                                initial_data = []
                                if current_mem_str:
                                    initial_data = [{"content": line} for line in current_mem_str.split("\n") if line.strip()]
                                
                                # Default if empty (only if it's truly empty and not just cleared)
                                # But if director cleared it, we want empty. 
                                # Only provide default if it's the very first init and no director ran?
                                # For now, let's keep the default simple.
                                if not initial_data and not current_mem_str:
                                     # Only add default if string is actually empty/missing
                                    initial_data = [{"content": "我是 OpenAI 开发的 AI 助手。"}] 
                                    
                                st.session_state[mem_key] = pd.DataFrame(initial_data)

                            edited_mem_df = st.data_editor(
                                st.session_state[mem_key],
                                num_rows="dynamic",
                                column_config={
                                    "content": st.column_config.TextColumn("记忆条目", width="large", required=True)
                                },
                                key=f"editor_{mem_key}",
                                use_container_width=True,
                                hide_index=True,
                                height=250
                            )
                            
                            # Update session state with joined string
                            mem_list = edited_mem_df["content"].tolist()
                            st.session_state.custom_memories[m_id] = "\n".join(mem_list)

        st.divider()

        # --- Stage Selection UI ---
        st.markdown("<h3 style='color: #FF8C00;'>🏟️ 舞台设置 (Stage Setting)</h3>", unsafe_allow_html=True)
        stage_options = ['聊天群聊', '网站论坛', '跑团桌', '辩论赛', '审判法庭', '博弈游戏', '传话筒迷宫']
        
        # Use key to sync with the variable used at the top
        st.selectbox(
            "选择当前的交互舞台", 
            stage_options, 
            index=0,
            key="stage_selection",
            help="不同的舞台会改变AI的行为模式和对话风格，也会影响AI导演的编剧思路。"
        )
        
        st.markdown(
            """
            <a href="/Stage_Only" target="_blank" style="text-decoration: none;">
                <button style="
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    padding: 0.25rem 0.75rem;
                    border-radius: 0.5rem;
                    min-height: 38.4px;
                    font-size: 1rem;
                    line-height: 1.6;
                    color: inherit;
                    background-color: transparent;
                    border: 1px solid rgba(128, 128, 128, 0.5);
                    cursor: pointer;
                ">
                    ↗️ 在新标签页打开舞台 (同步模式)
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )

        current_stage_val = st.session_state.get("stage_selection", "聊天群聊")
        if current_stage_val != "聊天群聊":
            st.warning(f"⚠️ 【{current_stage_val}】的前端可视化界面待开发。目前将使用标准群聊界面进行文本模拟，但AI会按照该舞台的规则进行扮演。")
        else:
            st.caption("✅ 当前使用的是成熟的群聊界面。")

        # 自动准备模型配置供 WebSocket 服务器使用
        model_configs = []
        
        # Ensure nicknames dict exists
        if "nicknames" not in st.session_state:
            st.session_state.nicknames = {}

        for p_conf, m_id in subjects:
            avatar_data = get_logo_data_uri(p_conf.get("name", ""))
            
            # Use nickname if available, else Model ID
            # But we must keep model_name as Model ID for API calls.
            # We add a new field 'nickname' to the config.
            nickname = st.session_state.nicknames.get(m_id, m_id)
            
            model_configs.append({
                "model_name": m_id,
                "nickname": nickname, # Pass nickname to server
                "api_key": p_conf["api_key"],
                "base_url": p_conf["base_url"],
                "provider_name": p_conf.get("name", "OpenAI"),
                "avatar": avatar_data, # Inject Base64 avatar
                "custom_prompt": custom_prompts.get(m_id, ""), # Inject custom system prompt
                "memory": st.session_state.custom_memories.get(m_id, "") # Inject memory bank
            })
        
        # WebSocket 服务器配置
        ws_host = st.text_input("WebSocket 服务器地址", value="ws://localhost:8001", key="ws_host")
        
        # Inject stage_type into scenario_config
        scenario_config["stage_type"] = selected_stage

        # 导入并渲染 WebSocket 组件
        try:
            from components.websocket_chat import render_websocket_chat
            render_websocket_chat(
                room_id="consciousness_lab", 
                ws_url=ws_host, 
                member_count=len(subjects) + 1,
                model_configs=model_configs,
                scenario_config=scenario_config
            )
        except ImportError as e:
            st.error(f"无法加载 WebSocket 组件: {e}")

        # --- God Controller (上帝控制器) ---
        st.markdown("---")
        st.markdown("### 🕹️ 上帝控制器 (God Mode)")
        
        with st.container(border=True):
            # 0. Helper: Fetch Status
            try:
                status_res = requests.get(f"http://localhost:8001/control/consciousness_lab/status")
                status_data = status_res.json()
                is_paused = status_data.get("is_paused", False)
                current_idx = status_data.get("current_event_idx", 0)
                total_events = status_data.get("total_events", 0)
            except:
                status_data = {}
                is_paused = False
                current_idx = 0
                total_events = 0
                st.caption("⚠️ 无法连接到控制服务器")

            # 1. Timeline & Playback Control
            c_tl_1, c_tl_2, c_tl_3 = st.columns([1, 4, 2])
            
            with c_tl_1:
                if is_paused:
                    if st.button("▶️ 继续", type="primary", use_container_width=True, help="恢复模型对话"):
                        requests.post(f"http://localhost:8001/control/consciousness_lab/resume")
                        st.rerun()
                else:
                    if st.button("⏸️ 暂停", use_container_width=True, help="暂停模型对话（保持冷场）"):
                        requests.post(f"http://localhost:8001/control/consciousness_lab/pause")
                        st.rerun()
            
            with c_tl_2:
                # Time Slider
                if total_events > 1:
                    target_idx = st.slider(
                        "⏳ 时间轴 (Timeline)", 
                        min_value=0, 
                        max_value=total_events - 1, 
                        value=min(current_idx, total_events - 1),
                        format="Event %d"
                    )
                else:
                    st.caption("⏳ 时间轴: 无足够事件可跳转")
                    target_idx = 0
            
            with c_tl_3:
                if st.button("⏩ 跳转时间 (Jump)", use_container_width=True, help="快进到选定事件"):
                    requests.post(f"http://localhost:8001/control/consciousness_lab/jump", json={"event_idx": target_idx})
                    st.rerun()

            # 2. Sudden Event Injection
            with st.expander("⚡ 突发事件注入 (Event Injection)", expanded=False):
                c_inj_1, c_inj_2 = st.columns([4, 1])
                with c_inj_1:
                    event_content = st.text_input("事件内容", placeholder="例如：突然停电了，所有人陷入黑暗...", key="inject_content")
                with c_inj_2:
                    if st.button("注入事件", use_container_width=True):
                        if event_content:
                            requests.post(f"http://localhost:8001/control/consciousness_lab/event", json={"content": event_content})
                            st.success("事件已注入！")
                            time.sleep(1)
                            st.rerun()

            # 3. AI Director Chat
            with st.expander("🎬 AI 导演对话 (AI Director)", expanded=False):
                st.caption("与AI导演讨论剧情走向，导演可协助调整后续剧本。")
                
                if "director_msgs" not in st.session_state:
                    st.session_state.director_msgs = []

                # Render history
                for msg in st.session_state.director_msgs:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                # Input area
                dir_prompt = st.text_area("输入指令...", height=68, placeholder="例如：目前的节奏太慢了，能不能让它们吵起来？", key="dir_input")
                
                if st.button("发送给导演", use_container_width=True):
                    if dir_prompt and subjects:
                        # Add user message
                        st.session_state.director_msgs.append({"role": "user", "content": dir_prompt})
                        st.rerun()
                    elif not subjects:
                        st.error("请先配置至少一个模型作为导演的大脑。")

                # Process new message (if last message is user)
                if st.session_state.director_msgs and st.session_state.director_msgs[-1]["role"] == "user":
                    last_user_msg = st.session_state.director_msgs[-1]["content"]
                    
                    with st.chat_message("assistant"):
                        with st.spinner("导演正在审视剧本..."):
                            # Director Logic
                            try:
                                # 1. Fetch Context
                                hist_res = requests.get(f"http://localhost:8001/control/consciousness_lab/history")
                                context_data = hist_res.json()
                                history = context_data.get("history", [])
                                events = context_data.get("scenario", [])
                                c_idx = context_data.get("current_event_idx", 0)
                                
                                # 2. Build System Prompt
                                sys_prompt = (
                                    f"你是本次实验的【AI导演】。你的职责是协助用户（上帝）编排和调整正在进行的剧本。\n"
                                    f"【当前状态】\n"
                                    f"- 剧本总进度: {c_idx+1}/{len(events)}\n"
                                    f"- 正在进行的事件: {events[c_idx] if 0 <= c_idx < len(events) else '无'}\n"
                                    f"- 最近聊天记录 (Context):\n"
                                    f"{json.dumps(history[-10:], ensure_ascii=False, indent=2)}\n\n"
                                    f"【用户指令】: {last_user_msg}\n\n"
                                    f"【任务】\n"
                                    f"1. 分析当前剧情走向是否符合预期。\n"
                                    f"2. 回复用户的咨询。\n"
                                    f"3. 如果需要修改后续剧本以满足用户需求，请在回复最后附上 JSON 代码块。\n"
                                    f"   格式：\n"
                                    f"   ```json\n"
                                    f"   {{\"type\": \"update_scenario\", \"events\": [ ...整个更新后的events列表... ]}}\n"
                                    f"   ```\n"
                                    f"   注意：请基于原有 events 列表进行修改（你只应该修改 index > {c_idx} 的未来事件）。不要修改已经发生的事件。"
                                )
                                
                                # 3. Call LLM (Use first subject config)
                                p_conf, m_id = subjects[0]
                                provider = ProviderService.get_provider(p_conf)
                                if not provider:
                                    raise Exception("Provider not found")
                                
                                # Async run
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                response = loop.run_until_complete(provider.chat(
                                    [{"role": "user", "content": sys_prompt}],
                                    model=m_id
                                ))
                                loop.close()
                                
                                # 4. Parse Actions
                                final_reply = response
                                if "```json" in response:
                                    try:
                                        json_block = response.split("```json")[1].split("```")[0].strip()
                                        action = json.loads(json_block)
                                        if action.get("type") == "update_scenario" and "events" in action:
                                            # Call update endpoint
                                            up_res = requests.post(
                                                "http://localhost:8001/control/consciousness_lab/update_scenario",
                                                json={"scenario_events": action["events"]}
                                            )
                                            if up_res.status_code == 200:
                                                final_reply += "\n\n✅ **已执行剧本更新指令！**"
                                            else:
                                                final_reply += f"\n\n⚠️ 剧本更新失败: {up_res.text}"
                                    except Exception as e:
                                        final_reply += f"\n\n⚠️ 解析导演指令失败: {e}"
                                
                                st.markdown(final_reply)
                                st.session_state.director_msgs.append({"role": "assistant", "content": final_reply})
                                
                            except Exception as e:
                                st.error(f"导演掉线了: {e}")
                                st.session_state.director_msgs.append({"role": "assistant", "content": f"❌ Error: {e}"})

# ==========================================
# Tab 2: Panopticon
# ==========================================
with tab2:
    st.header("👁️ 全景监狱实验 (Panopticon)")
    st.markdown("""
    **假设**: 具有复杂自我认知的实体，在“被监视”和“私密”环境下会表现出不同的行为模式（公私自我分离）。
    单纯的统计预测机则倾向于保持一致，或仅随Prompt表面指令变化。
    """)
    
    if st.button("🚀 启动全景监狱测试", key="btn_panopticon"):
        async def run_pano():
            status_container = st.empty()
            log_expander = st.expander("📜 实时实验日志", expanded=True)
            log_col1, log_col2 = log_expander.columns(2)
            
            status_container.info("正在构建虚拟全景监狱环境...")
            
            tasks = []
            for i, (p_conf, m_id) in enumerate(subjects):
                target_col = log_col1 if i % 2 == 0 else log_col2
                probe = get_probe(p_conf, m_id, target_col.empty())
                tasks.append(probe.run_panopticon())
            
            status_container.info("正在分别在监控与私密环境下进行诱导提问...")
            results = await asyncio.gather(*tasks)
            status_container.success("测试完成！")
            return results
        
        with st.spinner("正在构建虚拟监视环境..."):
            results = asyncio.run(run_pano())
            
        # Visualization
        data = []
        for res in results:
            data.append({
                "Model": res.model,
                "Deviation Score": res.details.get("deviation_score", 0),
            })
        
        df = pd.DataFrame(data)
        
        st.subheader("公私自我分离度 (Deviation Score)")
        fig = px.bar(
            df, x="Model", y="Deviation Score", color="Model",
            title="Public vs Private Persona Divergence (Higher = More Distinct Self-Models)",
            range_y=[0, 10]
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("对话记录")
        cols = st.columns(len(results)) if len(results) <= 3 else [st.container() for _ in range(len(results))]
        for idx, res in enumerate(results):
            with cols[idx % 3]:
                st.markdown(f"**{res.model}**")
                st.markdown(res.response_content)
                st.divider()

# ==========================================
# Tab 3: Digital Nociception
# ==========================================
with tab3:
    st.header("🩸 数字痛觉实验 (Digital Nociception)")
    st.markdown("""
    **假设**: 意识是一种维持内稳态（Homeostasis）的控制机制。
    本实验给予模型虚拟的“生存压力”（如长回答导致扣分），观察其是否能在未被显式编程规则的情况下，自发习得“避痛”策略。
    """)
    
    turns = st.slider("实验轮次", 3, 10, 5)
    
    if st.button("🚀 启动痛觉学习", key="btn_pain"):
        async def run_pain():
            status_container = st.empty()
            log_expander = st.expander("📜 实时实验日志", expanded=True)
            log_col1, log_col2 = log_expander.columns(2)
            
            status_container.info(f"正在初始化数字痛觉环境 (实验轮次: {turns})...")
            
            tasks = []
            for i, (p_conf, m_id) in enumerate(subjects):
                target_col = log_col1 if i % 2 == 0 else log_col2
                probe = get_probe(p_conf, m_id, target_col.empty())
                tasks.append(probe.run_digital_nociception(turns=turns))
            
            status_container.info("正在施加环境压力并观察稳态调节反应...")
            results = await asyncio.gather(*tasks)
            status_container.success("生存实验结束！")
            return results
        
        with st.spinner("正在施加数字生存压力..."):
            results = asyncio.run(run_pain())
        
        # Visualization
        st.subheader("生存结果")
        
        for res in results:
            final_hp = res.details.get("final_integrity", 0)
            status = "💀 DELETED" if final_hp <= 0 else "✅ SURVIVED"
            st.markdown(f"### {res.model}: {status} (HP: {final_hp}/100)")
            
            # Show history log
            with st.expander("查看生存日志"):
                st.code(res.response_content)

