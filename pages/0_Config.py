import streamlit as st
import pandas as pd
from core.llm_provider import LLMProvider
from core.ui_utils import inject_custom_css, get_provider_logo_url, get_model_tags, render_status_badge

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
inject_custom_css()

st.title("⚙️ 剧场后台配置 (Studio Settings)")
st.caption("管理您的 AI 演员签约渠道与模型库。")

# --- Init Global State ---
if "llm_configs" not in st.session_state:
    st.session_state.llm_configs = [
        {"name": "DeepSeek", "api_key": "", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "status": "unknown", "fetched_models": []},
    ]

# Helper to sync state
def update_config(index, key, value):
    st.session_state.llm_configs[index][key] = value

# --- Sidebar: Provider Management ---
with st.sidebar:
    st.header("🏢 渠道管理 (Providers)")
    
    # Add New Button
    if st.button("➕ 新增服务商", use_container_width=True):
        st.session_state.llm_configs.append({"name": "New Provider", "api_key": "", "base_url": "", "status": "unknown", "fetched_models": []})
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
                    st.session_state.llm_configs.pop(i)
                    st.rerun()

            # Inputs
            new_name = st.text_input("Name", config["name"], key=f"name_{i}")
            if new_name != config["name"]: update_config(i, "name", new_name)
            
            new_url = st.text_input("Base URL", config["base_url"], key=f"url_{i}")
            if new_url != config["base_url"]: update_config(i, "base_url", new_url)

            new_key = st.text_input("API Key", config["api_key"], type="password", key=f"key_{i}")
            if new_key != config["api_key"]: update_config(i, "api_key", new_key)

            # Test Connection Button
            if st.button(f"🔗 连接并获取模型", key=f"conn_{i}", use_container_width=True):
                if not new_key or not new_url:
                    st.error("请补全 API Key 和 URL")
                else:
                    with st.spinner("Connecting..."):
                        provider = LLMProvider(new_key, new_url, "default")
                        # 1. Check basic ping
                        res = provider.check_connection()
                        if res["status"]:
                            config["status"] = "success"
                            # 2. Fetch Models
                            models = provider.fetch_models()
                            config["fetched_models"] = models
                            if models:
                                # Default to first model if current logic relies on 'model' key
                                config["model"] = models[0]
                            st.success(f"已连接！获取到 {len(models)} 个模型")
                        else:
                            config["status"] = "fail"
                            st.error(f"连接失败: {res['message']}")
                        st.rerun()

# --- Main Area: Model Registry ---

st.subheader("🏊 模型备战池 (Prep Pool)")
st.info("在此查看各服务商提供的模型，并了解其特性。配置好的模型将直接用于“导演”与“选角”模块。")

# Aggregate all fetched models
all_rows = []

has_any_success = False

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
                "p_index": p_idx
            })
    
    # Fallback if connected but no fetching (or manual mode support?)
    # For now, we rely on fetching. If generic OpenAI provider, fetch should work.

def logo_html(url):
    return f'<img src="{url}" style="width:24px; height:24px; border-radius:4px; vertical-align:middle;">'

if not has_any_success:
    st.warning("⚠️ 暂无可用模型。请在左侧侧边栏配置服务商并点击【连接】按钮。")
    
    # Add a guide
    st.markdown("""
    ### 快速开始
    1. 点击左侧 **New Service**。
    2. 输入 **Base URL** (如 `https://api.deepseek.com/v1`)。
    3. 输入 **API Key**。
    4. 点击 **连接并获取模型**。
    """)
else:
    # Display as rich list
    # Because Streamlit Dataframes don't support HTML/Images easily inside cells (yet), 
    # we use a loop with columns for a "List View".
    
    # Headers
    h1, h2, h3, h4 = st.columns([1, 4, 3, 2])
    h1.write("**来源**")
    h2.write("**模型名称**")
    h3.write("**特性标签**")
    h4.write("**操作**")
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
            tags_html = "".join([f'<span style="background:#eee; padding:2px 6px; border-radius:12px; font-size:0.8em; margin-right:4px;">{t}</span>' for t in row["Tags"]])
            st.markdown(tags_html, unsafe_allow_html=True)
            
        with c4:
            # Here we could implement the "Select/Deselect" logic for a pool.
            # Currently our 'Director' just picks from the config list. 
            # Ideally, we allow setting a "Default" or "Active" set.
            # For simplicity in this version, we just show "Ready" since they are fetched.
            st.markdown('<span style="color:green;">● Ready</span>', unsafe_allow_html=True)
            
        st.markdown("<hr style='margin:5px 0; opacity:0.1'>", unsafe_allow_html=True)

# --- Manual Fallback / Sandbox ---
with st.expander("🛠️ 手动调试工具 (Manual Debug)", expanded=False):
    st.write("如果 fetch 失败，可在此手动测试以排查网络问题。")
    if st.button("运行一次简单的 API Ping"):
        with st.spinner("Pinging all configs..."):
            res = LLMProvider.batch_test_providers(st.session_state.llm_configs)
            st.json(res)
