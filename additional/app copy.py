import streamlit as st
import asyncio
import uuid
import pandas as pd
import time
import os
import subprocess

# Services & Core
from services.state_manager import state_manager
from services.provider_service import ProviderService
from core.model_registry import get_model_info, MODEL_METADATA, PROVIDER_PRESETS
from core.ui_utils import get_logo_data_uri, create_badge_data_uri, TAG_STYLES

# Initialize State
state_manager.initialize()

st.set_page_config(
    page_title="LLM 模型竞技场",
    page_icon="⚔️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    h1, h2, h3 {
        font-family: 'Microsoft YaHei', sans-serif;
    }
    .provider-box {
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .status-badge-success {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    .status-badge-fail {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚔️ LLM 模型竞技场")
st.markdown("配置服务商，挑选同量级选手，一决高下！")

# --- Helper Functions ---

def add_provider(preset=None):
    new_id = len(state_manager.providers)
    
    name = f"服务商 #{new_id + 1}"
    base_url = ""
    
    if preset:
        name = f"{preset.name} #{new_id + 1}"
        base_url = preset.base_url

    # We manipulate the list in memory, then trigger a save via state_manager setter if needed,
    # or rely on the reference update if we re-assign.
    # Best practice with our StateManager: modify the list then re-assign or call save explicitly if we exposed it.
    # Since StateManager.providers returns the list object, modifying it in place updates the session state.
    # But to trigger the setter (and save to disk), we need to re-assign or call a method.
    
    new_provider = {
        "id": new_id, 
        "uuid": str(uuid.uuid4()),
        "name": name,
        "base_url": base_url, 
        "api_key": "", 
        "models": [],
        "status": "unknown"
    }
    
    # Re-assign to trigger setter
    current_providers = state_manager.providers
    current_providers.append(new_provider)
    state_manager.providers = current_providers

def toggle_model_in_pool(provider_uuid, model_id):
    """Toggle model presence in the prep pool."""
    current_pool = state_manager.prep_pool
    existing = next((item for item in current_pool if item["provider_uuid"] == provider_uuid and item["model_id"] == model_id), None)
    
    if existing:
        current_pool.remove(existing)
    else:
        current_pool.append({"provider_uuid": provider_uuid, "model_id": model_id})
    
    state_manager.prep_pool = current_pool

# --- Sidebar: General Settings ---
with st.sidebar:
    st.header("⚙️ 总设置")
    if st.button("🔄 更新项目 (Git Pull)"):
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                st.success(f"更新成功！\n{result.stdout}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"更新失败:\n{result.stderr}")
        except Exception as e:
            st.error(f"执行出错: {e}")

# --- Sidebar: Provider Config ---
with st.sidebar:
    st.header("⚙️ 接入服务商")
    
    providers_to_update = state_manager.providers
    
    # We use an index to iterate because we might modify the list (delete)
    # But safely, we can iterate a copy or use indices.
    
    for i, p in enumerate(providers_to_update):
        # Ensure UUID exists (migration)
        if "uuid" not in p:
            p["uuid"] = str(uuid.uuid4())
            state_manager.update_provider_field(i, "uuid", p["uuid"])
            
        with st.expander(f"{p['name']} ({len(p['models'])} 模型)", expanded=True):
            # Delete button
            c1, c2 = st.columns([6, 1])
            with c2:
                if st.button("🗑️", key=f"del_{p['uuid']}", help="删除此配置"):
                    providers_to_update.pop(i)
                    state_manager.providers = providers_to_update
                    st.rerun()

            # Inputs
            # We use st.session_state keys to track input, then update via callback or direct assignment
            new_url = st.text_input(
                f"API 地址", 
                value=p["base_url"], 
                key=f"url_{p['uuid']}"
            )
            if new_url != p["base_url"]:
                state_manager.update_provider_field(i, "base_url", new_url)
                
            new_key = st.text_input(
                f"API Key", 
                value=p["api_key"], 
                type="password", 
                key=f"key_{p['uuid']}"
            )
            if new_key != p["api_key"]:
                state_manager.update_provider_field(i, "api_key", new_key)
            
            col_btn, col_status = st.columns([1, 2])
            with col_btn:
                if st.button(f"连接", key=f"btn_conn_{p['uuid']}"):
                    with st.spinner("..."):
                        models = asyncio.run(ProviderService.fetch_available_models(p["base_url"], p["api_key"]))
                        if models is not None:
                            state_manager.update_provider_field(i, "models", models)
                            state_manager.update_provider_field(i, "status", "success")
                            st.rerun()
                        else:
                            state_manager.update_provider_field(i, "status", "fail")
                            state_manager.update_provider_field(i, "models", [])
                            st.rerun()
            
            with col_status:
                if p["status"] == "success":
                    st.markdown(f'<span class="status-badge-success">已连接: {len(p["models"])}个模型</span>', unsafe_allow_html=True)
                elif p["status"] == "fail":
                    st.markdown('<span class="status-badge-fail">连接失败</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ➕ 添加服务商")
    
    preset_options = {p.name: p for p in PROVIDER_PRESETS}
    selected_preset_name = st.selectbox("选择配置模板", list(preset_options.keys()), key="preset_sel")
    
    if st.button("添加配置卡片"):
        selected_preset = preset_options[selected_preset_name]
        add_provider(selected_preset)
        st.rerun()

# --- Main Content: 竞技场 ---

# 1. 选手入场 (Model Selection with Dataframe)
st.subheader("1. 🏟️ 选手入场")

# Aggregate all models
all_model_rows = []
for i, p in enumerate(state_manager.providers):
    if p["status"] == "success" and p["models"]:
        for m in p["models"]:
            info = get_model_info(m)
            # Use UUID for robust selection tracking
            is_selected = any(item.get("provider_uuid") == p["uuid"] and item["model_id"] == m for item in state_manager.prep_pool)
            
            all_model_rows.append({
                "row_id": f"{p['uuid']}:{m}", # Unique composite key
                "Selected": is_selected,
                "Logo": get_logo_data_uri(p["name"]),
                "Tag": create_badge_data_uri(info.tags),
                "RawTags": info.tags,
                "Model ID": info.name,
                "Provider": p["name"],
                "Provider_UUID": p["uuid"],
                "Type": info.type,
                "Context Window": f"{info.context_window/1000:.0f}k" if info.context_window else "N/A",
                "Input Price ($/1M)": f"${info.input_price:.2f}",
                "Output Price ($/1M)": f"${info.output_price:.2f}",
                "Release Date": info.release_date or "Unknown",
                "Description": info.description
            })

if not all_model_rows:
    st.warning("👈 请先在左侧配置并连接至少一个 API 服务商，以获取参赛模型。")
else:
    # Display as Dataframe with selection
    df_models = pd.DataFrame(all_model_rows)
    # Don't set index to row_id yet if we want to use it easily, but usually convenient
    # df_models.set_index("row_id", inplace=True) 
    
    # --- Filter Section ---
    available_types = sorted(list(set(df_models["Type"].tolist())))
    
    # Extract unique tags
    all_tags = set()
    for tags in df_models["RawTags"]:
        if tags:
            all_tags.update(tags)
    available_tags = sorted(list(all_tags))
    
    TYPE_MAPPING = {
        "chat": "对话 (Chat)",
        "vision": "视觉 (Vision)",
        "reasoning": "推理 (Reasoning)",
        "code": "代码 (Code)",
        "embedding": "嵌入 (Embedding)",
        "audio": "音频 (Audio)",
        "video": "视频 (Video)",
        "image-generation": "绘图 (Image Gen)",
        "multimodal": "多模态 (Multimodal)"
    }

    with st.expander("🔍 筛选选项 (Filter Options)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            selected_types = st.multiselect(
                "按模型类型筛选",
                options=available_types,
                default=available_types,
                placeholder="选择模型类型...",
                format_func=lambda x: TYPE_MAPPING.get(x, x)
            )
        with c2:
            selected_tags = st.multiselect(
                "按标签筛选",
                options=available_tags,
                default=[],
                placeholder="选择标签 (留空显示所有)...",
                format_func=lambda x: TAG_STYLES.get(x, {}).get("text", x)
            )
    
    # Apply Filters
    df_filtered = df_models
    
    # Type Filter
    if selected_types:
        df_filtered = df_filtered[df_filtered["Type"].isin(selected_types)]
        
    # Tag Filter
    if selected_tags:
        df_filtered = df_filtered[df_filtered["RawTags"].apply(lambda x: any(tag in selected_tags for tag in x))]

    st.markdown("### 选手列表")
    
    # Header
    h1, h2, h3, h4, h5, h6 = st.columns([0.5, 4, 1.5, 1.5, 1.5, 2])
    h1.markdown("**选择**")
    h2.markdown("**模型 (Model)**")
    h3.markdown("**类型**")
    h4.markdown("**上下文**")
    h5.markdown("**价格(In/Out)**")
    h6.markdown("**来源**")
    st.divider()
    
    # Data Rows
    for idx, row in df_filtered.iterrows():
        # Layout: Checkbox | [Logo] Name [Tag] | Type | Context | Price | Provider
        c1, c2, c3, c4, c5, c6 = st.columns([0.5, 4, 1.5, 1.5, 1.5, 2])
        
        # 1. Checkbox
        is_selected = row["Selected"]
        
        # We need a unique key for the checkbox
        row_id = row["row_id"]
        
        def on_change_wrapper(rid=row_id):
            try:
                p_uuid, m_id = rid.split(":", 1)
                toggle_model_in_pool(p_uuid, m_id)
            except ValueError:
                pass

        c1.checkbox(
            "Select", 
            value=is_selected, 
            key=f"chk_{row_id}", 
            label_visibility="collapsed",
            on_change=on_change_wrapper
        )
        
        # 2. Rich Model Name: Logo + Name + Tag
        logo_html = f'<img src="{row["Logo"]}" style="height:20px; vertical-align:middle; margin-right:8px;">' if row["Logo"] else ''
        tag_html = f'<img src="{row["Tag"]}" style="height:20px; vertical-align:middle; margin-left:8px;">' if row["Tag"] else ''
        name_html = f'<span style="font-weight:600; font-size:1em; vertical-align:middle;">{row["Model ID"]}</span>'
        
        c2.markdown(f"""
        <div style="display:flex; align-items:center; height: 100%;">
            {logo_html}
            {name_html}
            {tag_html}
        </div>
        """, unsafe_allow_html=True)
        
        c3.markdown(f"<div style='margin-top: 5px;'>{row['Type']}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='margin-top: 5px;'>{row['Context Window']}</div>", unsafe_allow_html=True)
        c5.markdown(f"<div style='margin-top: 5px; font-size:0.9em;'>{row['Input Price ($/1M)']}<br>{row['Output Price ($/1M)']}</div>", unsafe_allow_html=True)
        c6.markdown(f"<div style='margin-top: 5px;'>{row['Provider']}</div>", unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 0.2em 0; opacity: 0.2;'>", unsafe_allow_html=True)

    if not df_filtered.empty:
        st.caption(f"共显示 {len(df_filtered)} 个模型")
    else:
        st.info("没有匹配的模型。")


# 2. 备战池 (Prep Pool)
st.subheader("2. 🏊 备战池")

if not state_manager.prep_pool:
    st.info("👈 请在上方列表中勾选参赛选手...")
else:
    # Interactive Pool with Remove Buttons
    cols = st.columns(4)
    for i, item in enumerate(state_manager.prep_pool):
        p_uuid = item.get("provider_uuid")
        m_id = item["model_id"]
        
        # Find provider name
        p_conf = next((p for p in state_manager.providers if p.get("uuid") == p_uuid), None)
        p_name = p_conf["name"] if p_conf else "Unknown"
        
        with cols[i % 4]:
            st.markdown(f"""
            <div style="border:1px solid #ddd; padding:10px; border-radius:10px; margin-bottom:10px; background:white;">
                <div style="font-weight:bold;">{m_id}</div>
                <div style="font-size:0.8em; color:#666;">{p_name}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("移除", key=f"rem_{p_uuid}_{m_id}"):
                toggle_model_in_pool(p_uuid, m_id)
                st.rerun()
