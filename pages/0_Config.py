import streamlit as st
import pandas as pd
from core.llm_provider import LLMProvider, LocalProviderScanner
from core.ui_utils import inject_custom_css, get_provider_logo_url, get_model_tags, render_status_badge
from core.state.manager import state_manager

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
inject_custom_css()

st.title("⚙️ 剧场后台配置 (Studio Settings)")
st.caption("管理您的 AI 演员签约渠道与模型库。")

# --- Init Global State ---
state_manager.initialize()

# Helper to sync state and PERSIST
def update_config(index, key, value):
    st.session_state.llm_configs[index][key] = value
    state_manager.db.save_provider(st.session_state.llm_configs[index])

# --- Presets ---
PRESETS = {
    "Custom (自定义)": {"name": "New Provider", "base_url": ""},
    "OpenAI": {"name": "OpenAI", "base_url": "https://api.openai.com/v1"},
    "DeepSeek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
    "SiliconFlow (硅基流动)": {"name": "SiliconFlow", "base_url": "https://api.siliconflow.cn/v1"},
    "Claude (Anthropic)": {"name": "Claude", "base_url": "https://api.anthropic.com/v1"},
    "Google Gemini": {"name": "Google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "Moonshot (Kimi)": {"name": "Moonshot", "base_url": "https://api.moonshot.cn/v1"},
    "AliCloud Qwen (通义千问)": {"name": "Qwen", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "Zhipu ChatGLM (智谱)": {"name": "ChatGLM", "base_url": "https://open.bigmodel.cn/api/paas/v4/"},
    "ByteDance Ark (火山引擎)": {"name": "ByteDance", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "01.AI (零一万物)": {"name": "01.AI", "base_url": "https://api.lingyiwanwu.com/v1"},
    "Baichuan (百川智能)": {"name": "Baichuan", "base_url": "https://api.baichuan-ai.com/v1"},
    "Tencent Hunyuan (腾讯混元)": {"name": "Hunyuan", "base_url": "https://api.hunyuan.cloud.tencent.com/v1"},
    "Xiaomi MiLM (小米)": {"name": "Xiaomi", "base_url": "https://api.ai.mi.com/v1"},
    "Xiaomi MiMo (小米MiMo)": {"name": "MiMo", "base_url": "https://api.xiaomimimo.com/v1"},
    "Minimax (海螺)": {"name": "Minimax", "base_url": "https://api.minimax.chat/v1"},
    "StepFun (阶跃星辰)": {"name": "StepFun", "base_url": "https://api.stepfun.com/v1"},
    "OpenRouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
    "Groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    "Together AI": {"name": "Together", "base_url": "https://api.together.xyz/v1"},
    "Mistral AI": {"name": "Mistral", "base_url": "https://api.mistral.ai/v1"},
    "Perplexity": {"name": "Perplexity", "base_url": "https://api.perplexity.ai"},
}

# --- Sidebar: Provider Management ---
with st.sidebar:
    st.header("🏢 渠道管理 (Providers)")
    
    # Add New with Presets
    with st.expander("➕ 新增服务商", expanded=False):
        preset_choice = st.selectbox("选择预设或自定义", list(PRESETS.keys()))
        if st.button("确认添加", use_container_width=True):
            p = PRESETS[preset_choice]
            new_provider = {
                "name": p["name"], 
                "api_key": "", 
                "base_url": p["base_url"], 
                "model": "default", 
                "status": "unknown", 
                "fetched_models": []
            }
            # Avoid name collision
            base_name = new_provider["name"]
            counter = 1
            while any(c["name"] == new_provider["name"] for c in st.session_state.llm_configs):
                new_provider["name"] = f"{base_name} ({counter})"
                counter += 1
                
            st.session_state.llm_configs.append(new_provider)
            state_manager.db.save_provider(new_provider)
            st.rerun()
        
    if st.button("🔍 扫描本地 (Ollama/LM Studio)", use_container_width=True):
        with st.spinner("Scanning for local providers..."):
            detected = LocalProviderScanner.scan_common_ports()
            new_count = 0
            for d in detected:
                # Avoid duplicates
                if not any(c["base_url"] == d["base_url"] for c in st.session_state.llm_configs):
                    st.session_state.llm_configs.append(d)
                    state_manager.db.save_provider(d)
                    new_count += 1
            if new_count > 0:
                st.success(f"发现 {new_count} 个新本地服务端")
            else:
                st.info("未发现新的本地服务端")
            st.rerun()

    if st.button("🗑️ 清空所有配置", use_container_width=True, type="secondary"):
        for cfg in st.session_state.llm_configs:
            state_manager.db.delete_provider(cfg["name"])
        st.session_state.llm_configs = []
        st.rerun()

    # Loop Configs (using list copy to allow safe mutation if needed, though we operate on index)
    for i, config in enumerate(st.session_state.llm_configs):
        status_html = render_status_badge(config.get("status", "unknown"))
        model_count = len(config.get("fetched_models", []))
        
        with st.expander(f"{config['name']} ({model_count} models)", expanded=False):
            # Header with Delete
            c_head_1, c_head_2 = st.columns([4, 1])
            with c_head_1:
                st.markdown(status_html, unsafe_allow_html=True)
            with c_head_2:
                if st.button("🗑️", key=f"del_{i}"):
                    target = st.session_state.llm_configs.pop(i)
                    state_manager.db.delete_provider(target["name"])
                    st.rerun()

            # Inputs
            new_name = st.text_input("Name", config["name"], key=f"name_{i}")
            if new_name != config["name"]: update_config(i, "name", new_name)
            
            new_url = st.text_input("Base URL", config["base_url"], key=f"url_{i}")
            if new_url != config["base_url"]: update_config(i, "base_url", new_url)

            new_key = st.text_input("API Key", config["api_key"], type="password", key=f"key_{i}")
            if new_key != config["api_key"]: update_config(i, "api_key", new_key)

            # Test Connection Button
            if st.button(f"🔗 连接并在云端获取模型", key=f"conn_{i}", use_container_width=True):
                if not new_key or not new_url:
                    st.error("请补全 API Key 和 URL")
                else:
                    with st.spinner("Connecting..."):
                        # Use the current selected model for check OR default
                        current_model = config.get("model", "default")
                        provider = LLMProvider(new_key, new_url, current_model)
                        
                        # 1. Check connection
                        res = provider.check_connection()
                        if res["status"]:
                            config["status"] = "success"
                            # 2. Fetch Models
                            models = provider.fetch_models()
                            if models:
                                config["fetched_models"] = models
                                # If the current model is not in the list, set it to the first one
                                if config.get("model") not in models:
                                    config["model"] = models[0]
                                st.success(f"已连接！获取到 {len(models)} 个模型")
                            else:
                                config["fetched_models"] = []
                                st.warning("已连接，但未能获取到模型列表。请在下方手动输入。")
                        else:
                            config["status"] = "fail"
                            st.error(f"连接失败: {res['message']}")
                        
                        # PERSIST status/models
                        state_manager.db.save_provider(config)
                        st.rerun()

            # Connection Success UI: Model Selection
            if config.get("status") == "success":
                models = config.get("fetched_models", [])
                if models:
                    selected_model = st.selectbox(
                        "选择活跃模型 (Active Model)", 
                        options=models, 
                        index=models.index(config["model"]) if config.get("model") in models else 0,
                        key=f"select_m_{i}"
                    )
                    if selected_model != config.get("model"):
                        config["model"] = selected_model
                        state_manager.db.save_provider(config)
                        st.rerun()
                else:
                    # Manual Model Input (fallback)
                    st.info("💡 自动获取失败，请手动录入模型 ID")
                    m_input = st.text_input("模型 ID (如 mimo-v2-flash)", key=f"manual_m_{i}")
                    if st.button("锁定手动模型", key=f"btn_m_{i}", use_container_width=True):
                        if m_input:
                            config["fetched_models"] = [m_input]
                            config["model"] = m_input
                            state_manager.db.save_provider(config)
                            st.rerun()

# --- Main Area: Model Registry ---

st.subheader("🏊 模型备战池 (Prep Pool)")
st.info("在此查看各服务商提供的模型。你可以点击 ⭐ 收藏模型，收藏的模型将优先显示并用于导演选角。")

# --- Initialize Favorites in Session State ---
if "favorite_models" not in st.session_state:
    st.session_state.favorite_models = set()

def logo_html(url):
    return f'<img src="{url}" style="width:24px; height:24px; border-radius:4px; vertical-align:middle;">'

# Aggregate all fetched models
all_rows = []
has_any_success = False

# Heartbeat Check
if st.button("💓 刷新全局连贯性 (Heartbeat)", use_container_width=True):
    with st.spinner("Checking provider status..."):
        heartbeats = LocalProviderScanner.run_heartbeat(st.session_state.llm_configs)
        # Update local status based on heartbeats
        for hb in heartbeats:
            for cfg in st.session_state.llm_configs:
                if cfg.get("name") == hb["id"]:
                    cfg["status"] = "success" if hb["active"] else "fail"
                    cfg["latency"] = hb["latency"]
                    # Persist status change
                    state_manager.db.save_provider(cfg)
        st.rerun()

for p_idx, config in enumerate(st.session_state.llm_configs):
    if config.get("fetched_models"):
        has_any_success = True
        provider_name = config["name"]
        logo_url = get_provider_logo_url(provider_name)
        
        for m_id in config["fetched_models"]:
            tags = get_model_tags(m_id)
            all_rows.append({
                "Logo": logo_html(logo_url),
                "Model ID": m_id,
                "Provider": provider_name,
                "Tags": tags,
                "p_index": p_idx,
                "is_fav": m_id in st.session_state.favorite_models
            })


if not has_any_success:
    st.warning("⚠️ 暂无可用模型。请在左侧侧边栏配置服务商并点击【连接】按钮。")
else:
    # Sorting: Favorites first
    all_rows.sort(key=lambda x: x["is_fav"], reverse=True)

    # Filter/Search Bar
    search_q = st.text_input("🔍 搜索模型或标签...", placeholder="例如: gpt-4, vision, deepseek")
    
    if search_q:
        all_rows = [r for r in all_rows if search_q.lower() in r["Model ID"].lower() or any(search_q.lower() in t.lower() for t in r["Tags"])]

    # Headers
    h1, h2, h3, h4 = st.columns([1, 4, 3, 2])
    h1.write("**状态**")
    h2.write("**模型名称**")
    h3.write("**特性标签**")
    h4.write("**收藏**")
    st.divider()

    for row in all_rows:
        c1, c2, c3, c4 = st.columns([1, 4, 3, 2])
        
        with c1:
            st.markdown(row["Logo"], unsafe_allow_html=True)
            
        with c2:
            st.write(f"**{row['Model ID']}**")
            st.caption(row["Provider"])
            
        with c3:
            # Render tags as badges
            tags_html = "".join([f'<span style="background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); padding:2px 8px; border-radius:12px; font-size:0.75em; margin-right:4px; color:#ccc;">{t}</span>' for t in row["Tags"]])
            st.markdown(tags_html, unsafe_allow_html=True)
            
        with c4:
            fav_icon = "⭐" if row["is_fav"] else "☆"
            if st.button(fav_icon, key=f"fav_{row['Model ID']}_{row['p_index']}"):
                if row["is_fav"]:
                    st.session_state.favorite_models.remove(row["Model ID"])
                else:
                    st.session_state.favorite_models.add(row["Model ID"])
                st.rerun()
            
        st.markdown("<hr style='margin:5px 0; opacity:0.1'>", unsafe_allow_html=True)

# --- Manual Fallback / Sandbox ---
with st.expander("🛠️ 手动调试工具 (Manual Debug)", expanded=False):
    st.write("如果 fetch 失败，可在此手动测试以排查网络问题。")
    if st.button("运行一次简单的 API Ping"):
        with st.spinner("Pinging all configs..."):
            res = LLMProvider.batch_test_providers(st.session_state.llm_configs)
            st.json(res)
