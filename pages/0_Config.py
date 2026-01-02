import streamlit as st
import pandas as pd
import requests
import concurrent.futures
import time

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")

from core.llm_provider import LLMProvider, LocalProviderScanner
from core.ui_utils import inject_custom_css, get_provider_logo_url, get_model_tags, render_status_badge
from core.state.manager import state_manager
inject_custom_css()

st.title("⚙️ 剧场后台配置 (Studio Settings)")
st.caption("管理您的 AI 演员签约渠道与模型库。")

# --- Init Global State ---
state_manager.initialize()

# Helper to sync state and PERSIST
def update_config(index, key, value):
    st.session_state.llm_configs[index][key] = value
    state_manager.db.save_provider(st.session_state.llm_configs[index])

# Helper for Qwen Filtering
def is_valid_qwen_model(model_id):
    # Filter out known non-text models from DashScope
    # Added more keywords based on DashScope documentation
    excluded_keywords = [
        # Image Generation
        "wanx", "wordart", "facechain", "stable-diffusion", "image",
        # Audio/Speech (TTS & ASR)
        "paraformer", "sambert", "cosyvoice", "audio", "speech", "tts", "voice", "synthesis", "recognition",
        # Embeddings & Rerank (Not Chat)
        "embedding", "rerank", "bge", "gte",
        # Video
        "video", "animate",
        # Others
        "docmind"
    ]
    return not any(k in model_id.lower() for k in excluded_keywords)

def run_single_model_test(task):
    """
    Helper to test a single model's latency.
    Includes special handling for "Thinking/Reasoning" models to avoid false positives.
    """
    from openai import OpenAI
    
    model_id = task["model_id"].lower()
    
    # 1. Detect Thinking/Reasoning Models (o1, r1, reasoner)
    is_thinking = any(k in model_id for k in ["o1", "r1", "reason", "think"])
    
    # 2. Adjust Constraints
    timeout_val = 60 if is_thinking else 10
    max_tokens_val = 10 if is_thinking else 1
    
    try:
        client = OpenAI(api_key=task["api_key"], base_url=task["base_url"])
        start = time.time()
        
        client.chat.completions.create(
            model=task["model_id"],
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=max_tokens_val,
            timeout=timeout_val
        )
        return (time.time() - start) * 1000
    except Exception:
        return -1

# --- Tabs ---
tab_openrouter, tab_general = st.tabs(["🌐 OpenRouter 专属配置", "🏢 通用渠道管理"])

# ==============================================================================
# TAB 1: OpenRouter 专属配置 (OpenRouter Dedicated Config)
# ==============================================================================
with tab_openrouter:
    st.subheader("🌐 OpenRouter 模型库 (Model Registry)")
    st.caption("直接从 OpenRouter API 获取最新的模型列表、价格与参数信息。")

    # --- OpenRouter Configuration Section ---
    or_config_index = -1
    or_config = None
    for i, cfg in enumerate(st.session_state.llm_configs):
        if "openrouter.ai" in cfg.get("base_url", ""):
            or_config_index = i
            or_config = cfg
            break
    
    with st.expander("🔑 OpenRouter API 设置 (API Settings)", expanded=not (or_config and or_config.get("api_key"))):
        col_key, col_btn = st.columns([4, 1])
        with col_key:
            or_api_key = st.text_input("OpenRouter API Key", value=or_config.get("api_key", "") if or_config else "", type="password", label_visibility="collapsed", placeholder="sk-or-...", key="input_or_key")
        with col_btn:
            if st.button("💾 保存配置", key="btn_save_or_key", use_container_width=True):
                if not or_api_key:
                    st.error("请输入 API Key")
                else:
                    new_conf = {
                        "name": "OpenRouter",
                        "base_url": "https://openrouter.ai/api/v1",
                        "api_key": or_api_key,
                        "model": "default",
                        "fetched_models": [],
                        "status": "unknown"
                    }
                    
                    if or_config_index != -1:
                        st.session_state.llm_configs[or_config_index]["api_key"] = or_api_key
                        st.session_state.llm_configs[or_config_index]["base_url"] = "https://openrouter.ai/api/v1"
                        state_manager.db.save_provider(st.session_state.llm_configs[or_config_index])
                    else:
                        st.session_state.llm_configs.append(new_conf)
                        state_manager.db.save_provider(new_conf)
                    
                    st.success("已保存")
                    st.rerun()

    st.divider()

    # Constants
    OPENROUTER_MODELS_API = "https://openrouter.ai/api/v1/models"

    def fetch_openrouter_models():
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            # Increased timeout to 20s for better stability
            response = session.get(OPENROUTER_MODELS_API, timeout=20) 
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            st.error(f"Failed to fetch models: {e}")
            return []

    def process_models_data(models_data):
        import time

        processed = []
        now = time.time()
        # Define "New" as created within last 30 days
        thirty_days_ago = now - (30 * 24 * 60 * 60)

        # Translation Helper
        MODALITY_MAP = {
            "text->text": "文本对话 (Text)",
            "text+image->text": "多模态视觉 (Vision)",
            "text->image": "文生图 (Image Gen)",
            "unknown": "未知 (Unknown)"
        }

        for m in models_data:
            # Pricing
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", 0)) * 1_000_000
            completion_price = float(pricing.get("completion", 0)) * 1_000_000
            
            is_free = (prompt_price == 0 and completion_price == 0)
            
            # Context
            context_len = int(m.get("context_length", 0))

            # New check
            created_ts = m.get("created")
            is_new = False
            if created_ts:
                try:
                    if float(created_ts) > thirty_days_ago:
                        is_new = True
                except:
                    pass

            # Modality
            arch = m.get("architecture", {})
            modality_raw = arch.get("modality", "unknown")
            modality_cn = MODALITY_MAP.get(modality_raw, modality_raw)

            # Tags
            tags = []
            if is_free: tags.append("🆓 免费")
            if is_new: tags.append("🆕 新品")
            if "image" in modality_raw: tags.append("👀 视觉")
            if context_len >= 128000: tags.append("📚 长上下文")
            if (prompt_price + completion_price) < 1.0 and not is_free: tags.append("💰 经济")
            if (prompt_price + completion_price) > 10.0: tags.append("💎 高级")

            tag_str = " ".join(tags)

            # Provider extraction
            model_id = m.get("id", "")
            provider_name = model_id.split("/")[0] if "/" in model_id else "Unknown"

            processed.append({
                "选择 (Select)": False, # Checkbox column
                "模型厂商 (Provider)": provider_name,
                "ID": model_id, # Kept for search, hidden in view
                "模型名称 (Name)": m.get("name"),
                "标签 (Tags)": tag_str,
                "上下文长度 (Context)": context_len,
                "输入价格 ($/1M)": prompt_price, # Keep as float for sorting
                "输出价格 ($/1M)": completion_price, # Keep as float for sorting
                "模态 (Modality)": modality_cn,
                "模型描述 (Description)": m.get("description", "")
            })
        return pd.DataFrame(processed)

    # --- OpenRouter UI ---
    
    should_rerun = False

    # --- Auto-Translation Processor (Real-time Feedback) ---
    if "trans_queue" in st.session_state and st.session_state.trans_queue:
        # Get OpenRouter Config
        or_config = None
        for cfg in st.session_state.llm_configs:
            if "openrouter.ai" in cfg.get("base_url", ""):
                or_config = cfg
                break
        
        if not or_config or not or_config.get("api_key"):
            st.error("OpenRouter 配置丢失，翻译中止。")
            st.session_state.trans_queue = [] # Stop
        else:
            # Progress UI
            total = st.session_state.get("trans_total", 1)
            remaining = len(st.session_state.trans_queue)
            completed = total - remaining
            
            st.info(f"🔄 正在翻译中... ({completed}/{total}) - 实时更新中")
            st.progress(completed / total)
            
            # Process One Item
            target_model_id = st.session_state.trans_queue[0]
            translator_id = st.session_state.get("trans_translator_id")
            
            # Find row in DF
            mask = st.session_state.or_models_df["ID"] == target_model_id
            
            if mask.any():
                current_desc = st.session_state.or_models_df.loc[mask, "模型描述 (Description)"].values[0]
                model_name = st.session_state.or_models_df.loc[mask, "模型名称 (Name)"].values[0]
                
                # Check if needs translation (not empty)
                if current_desc:
                    try:
                        from core.llm_provider import LLMProvider
                        provider = LLMProvider(
                            api_key=or_config["api_key"],
                            base_url=or_config["base_url"],
                            model_name=translator_id
                        )
                        
                        prompt = f"Translate the following AI model description to Chinese. Keep it concise and professional. Do not add explanations. Text: {current_desc}"
                        
                        if provider.client:
                            resp = provider.client.chat.completions.create(
                                model=provider.model_name,
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.3,
                                max_tokens=500
                            )
                            translated_text = resp.choices[0].message.content.strip()
                            
                            # Update State (This is the "Show where" part - updating the source of truth)
                            st.session_state.or_models_df.loc[mask, "模型描述 (Description)"] = translated_text
                            
                    except Exception as e:
                        error_msg = f"模型 [{model_name}] 翻译失败: {str(e)}"
                        if "translation_errors" not in st.session_state:
                            st.session_state.translation_errors = []
                        st.session_state.translation_errors.append(error_msg)

            # Move to next
            st.session_state.trans_queue.pop(0)
            
            # Check if done
            if not st.session_state.trans_queue:
                st.success("全部翻译完成！")
                # Uncheck translator
                if translator_id:
                    mask_trans = st.session_state.or_models_df["ID"] == translator_id
                    st.session_state.or_models_df.loc[mask_trans, "选择 (Select)"] = False
                # Allow fall-through to render the final state
            else:
                should_rerun = True

    # Display persistent errors if any
    if "translation_errors" in st.session_state and st.session_state.translation_errors:
        with st.container():
            st.error(f"⚠️ 翻译过程中发生了 {len(st.session_state.translation_errors)} 个错误：")
            for err in st.session_state.translation_errors:
                st.text(f"❌ {err}")
            if st.button("清除报错信息 (Clear Errors)", key="clear_trans_errors"):
                st.session_state.translation_errors = []
                st.rerun()

    col1, col2, col3 = st.columns([2, 4, 2])
    
    with col1:
        if st.button("🔄 刷新 OpenRouter 模型列表", type="primary", key="btn_refresh_or", use_container_width=True):
            with st.spinner("Fetching from OpenRouter..."):
                models = fetch_openrouter_models()
                if models:
                    st.session_state.openrouter_models = models
                    st.success(f"成功获取 {len(models)} 个模型。")
                else:
                    st.warning("未找到模型或发生错误。")

    with col2:
        # Search/Filter
        search_term = st.text_input("🔍 搜索模型 (Search)", "", key="search_or", label_visibility="collapsed", placeholder="🔍 搜索模型名称或ID...")
        
        # Tag Filter
        all_tags = set()
        if "or_models_df" in st.session_state and not st.session_state.or_models_df.empty:
            for tags_str in st.session_state.or_models_df["标签 (Tags)"]:
                if tags_str:
                    for t in tags_str.split():
                        all_tags.add(t)
        sorted_tags = sorted(list(all_tags))
        
        selected_tags = st.multiselect(
            "🏷️ 按标签筛选 (Filter by Tags)", 
            options=sorted_tags,
            placeholder="选择标签以过滤模型池...",
        )

    with col3:
        translate_btn = st.button("🌐 一键翻译描述", help="使用勾选的模型作为翻译引擎，翻译列表中所有模型的描述", use_container_width=True)

    if "openrouter_models" in st.session_state and st.session_state.openrouter_models:
        # Check if we need to initialize or update the dataframe in session state
        # We store the dataframe in session state to persist checkbox selections across reruns
        if "or_models_df" not in st.session_state or len(st.session_state.or_models_df) != len(st.session_state.openrouter_models):
             st.session_state.or_models_df = process_models_data(st.session_state.openrouter_models)
        
        df = st.session_state.or_models_df
        
        # Apply Search Filter (create a copy for view, but we need to map back edits)
        # Note: Filtering makes editing tricky in Streamlit. 
        # Strategy: We show the dataframe. If user edits, we update the main DF.
        
        # To handle filtering correctly with data_editor, we usually just filter the view.
        # But data_editor returns the edited dataframe.
        
        filtered_df = df
        
        # 1. Tag Filter (AND Logic)
        if selected_tags:
            def has_all_tags(row_tags_str, selected):
                if not row_tags_str: return False
                row_tags = row_tags_str.split()
                # Check if row_tags contains ALL selected tags (Subset check)
                return set(selected).issubset(set(row_tags))
            
            mask = filtered_df["标签 (Tags)"].apply(lambda x: has_all_tags(x, selected_tags))
            filtered_df = filtered_df[mask]

        # 2. Search Filter
        if search_term:
            filtered_df = filtered_df[filtered_df["ID"].str.contains(search_term, case=False) | filtered_df["模型名称 (Name)"].str.contains(search_term, case=False)]

        # --- Sync Filtered Result to OpenRouter Provider Config (The Pool) ---
        # Find OpenRouter Config
        or_config_idx = -1
        for i, cfg in enumerate(st.session_state.llm_configs):
            if "openrouter.ai" in cfg.get("base_url", ""):
                or_config_idx = i
                break
        
        if or_config_idx != -1:
            # Get current visible IDs (This is the pool defined by filters)
            visible_ids = filtered_df["ID"].tolist()
            
            # Update if changed (Check lengths first for speed, then set comparison)
            current_stored = st.session_state.llm_configs[or_config_idx].get("fetched_models", [])
            
            # Simple check: if list content changed
            if set(visible_ids) != set(current_stored):
                 st.session_state.llm_configs[or_config_idx]["fetched_models"] = visible_ids
                 # Persist to DB immediately so it's safe
                 state_manager.db.save_provider(st.session_state.llm_configs[or_config_idx])

        # Display Data Editor

        # Display Data Editor
        edited_df = st.data_editor(
            filtered_df,
            column_config={
                "选择 (Select)": st.column_config.CheckboxColumn("选择", help="勾选以翻译描述", default=False, width="small"),
                "模型厂商 (Provider)": st.column_config.TextColumn("厂商 (Provider)", width="small"),
                "ID": None, # Hide Model ID
                "模型名称 (Name)": st.column_config.TextColumn("模型名称 (Name)", width="medium"),
                "标签 (Tags)": st.column_config.TextColumn("标签 (Tags)", width="small"),
                "上下文长度 (Context)": st.column_config.NumberColumn("上下文长度", help="Context Length", format="%d", width="small"),
                "输入价格 ($/1M)": st.column_config.NumberColumn("输入价格", help="Input Price ($/1M)", format="$%.4f", width="small"),
                "输出价格 ($/1M)": st.column_config.NumberColumn("输出价格", help="Output Price ($/1M)", format="$%.4f", width="small"),
                "模态 (Modality)": st.column_config.TextColumn("模态 (Modality)", width="small"),
                "模型描述 (Description)": st.column_config.TextColumn("模型描述 (Description)", width="large"),
            },
            use_container_width=True,
            hide_index=True,
            height=600,
            disabled=["模型厂商 (Provider)", "模型名称 (Name)", "标签 (Tags)", "上下文长度 (Context)", "输入价格 ($/1M)", "输出价格 ($/1M)", "模态 (Modality)", "模型描述 (Description)"],
            key="or_editor"
        )
        
        # Handle Translation Logic
        if translate_btn:
            # Clear previous errors
            st.session_state.translation_errors = []

            # 1. Identify the Translator Model (The one checked by user)
            selected_rows = edited_df[edited_df["选择 (Select)"] == True]
            
            if selected_rows.empty:
                st.warning("请勾选一个模型作为【翻译引擎】！(Please select a model to act as the translator)")
            elif len(selected_rows) > 1:
                st.warning("请只勾选一个模型作为翻译引擎！(Please select only ONE model)")
            else:
                # Get the translator model details
                translator_row = selected_rows.iloc[0]
                translator_model_id = translator_row["ID"]
                translator_name = translator_row["模型名称 (Name)"]
                
                # 2. Find OpenRouter Config (to get API Key check)
                or_config = None
                for cfg in st.session_state.llm_configs:
                    if "openrouter.ai" in cfg.get("base_url", ""):
                        or_config = cfg
                        break
                
                if not or_config or not or_config.get("api_key"):
                    st.error("未找到 OpenRouter 配置或 API Key！请先在页面顶部的“OpenRouter API 设置”中填写 Key。")
                else:
                    # 3. Initialize Auto-Translation Queue
                    # We want to translate ALL rows currently visible in the editor (filtered or not)
                    # edited_df contains the current view
                    target_ids = edited_df["ID"].tolist()
                    
                    st.session_state.trans_queue = target_ids
                    st.session_state.trans_total = len(target_ids)
                    st.session_state.trans_translator_id = translator_model_id
                    
                    st.info(f"即将使用 [{translator_name}] 翻译 {len(target_ids)} 个模型...")
                    st.rerun()

    else:
        st.info("点击上方按钮获取 OpenRouter 模型列表。")
    
    if should_rerun:
        st.rerun()



# ==============================================================================
# TAB 2: 通用渠道管理 (General Provider Management)
# ==============================================================================
with tab_general:
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
            # Skip OpenRouter in General Tab (Managed in Tab 1)
            if config.get("name") == "OpenRouter" or "openrouter.ai" in config.get("base_url", ""):
                continue

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
                                
                                # Qwen Filter: Remove non-text models
                                # More robust check: Check name (case-insensitive) OR url
                                is_qwen = "qwen" in config.get("name", "").lower() or "dashscope" in new_url.lower()
                                
                                if is_qwen and models:
                                    original_count = len(models)
                                    models = [m for m in models if is_valid_qwen_model(m)]
                                    filtered_count = len(models)
                                    
                                    if filtered_count < original_count:
                                        st.toast(f"🧹 已自动过滤 {original_count - filtered_count} 个非文本模型 (如 Wanx/CosyVoice)")

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
        
    if "model_test_results" not in st.session_state:
        st.session_state.model_test_results = {}

    def logo_html(url):
        return f'<img src="{url}" style="width:24px; height:24px; border-radius:4px; vertical-align:middle;">'

    # Aggregate all fetched models
    all_rows = []
    has_any_success = False

    # Heartbeat Check & Test Response
    col_hb, col_test = st.columns([1, 1])
    
    with col_hb:
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

    with col_test:
        if st.button("⚡ 测试所有模型响应 (Test Response)", help="发送'Hi'并限制1 token，检测实际响应速度", use_container_width=True):
            tasks = []
            for config in st.session_state.llm_configs:
                # Skip OpenRouter (Tab 1)
                if config.get("name") == "OpenRouter" or "openrouter.ai" in config.get("base_url", ""):
                    continue
                if not config.get("fetched_models"):
                    continue
                
                # Check Key/URL
                if not config.get("api_key") or not config.get("base_url"):
                    continue
                    
                for m_id in config.get("fetched_models"):
                    tasks.append({
                        "api_key": config["api_key"],
                        "base_url": config["base_url"],
                        "model_id": m_id
                    })
            
            if not tasks:
                st.warning("没有可测试的模型 (No models found to test).")
            else:
                st.session_state.model_test_results = {} # Reset
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                completed = 0
                total = len(tasks)
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 50)) as executor:
                    future_to_model = {executor.submit(run_single_model_test, t): t["model_id"] for t in tasks}
                    
                    st.toast(f"🚀 已并发发起 {len(tasks)} 个测试请求...", icon="⚡")
                    
                    for future in concurrent.futures.as_completed(future_to_model):
                        m_id = future_to_model[future]
                        result = future.result()
                        st.session_state.model_test_results[m_id] = result
                        
                        completed += 1
                        progress = completed / total
                        progress_bar.progress(progress)
                        status_text.text(f"Testing... {completed}/{total}")
                
                status_text.empty()
                progress_bar.empty()
                
                # Report
                failed_count = sum(1 for v in st.session_state.model_test_results.values() if v < 0)
                st.success(f"测试完成！(共 {total} 个模型，{failed_count} 个失败)")
                
                # Auto-Clean Button logic will be handled below (outside the loop to be persistent)
                st.rerun()

    if st.session_state.get("model_test_results"):
        failed_models = [m for m, lat in st.session_state.model_test_results.items() if lat < 0]
        if failed_models:
            st.warning(f"⚠️ 检测到 {len(failed_models)} 个模型响应失败/超时 (已用红色标记)")
            if st.button(f"🧹 一键移除这 {len(failed_models)} 个无效模型 (Clean Failed Models)", type="primary"):
                removed_count = 0
                for cfg in st.session_state.llm_configs:
                    if not cfg.get("fetched_models"): continue
                    
                    original_len = len(cfg["fetched_models"])
                    # Filter out failed models
                    cfg["fetched_models"] = [m for m in cfg["fetched_models"] if m not in failed_models]
                    
                    if len(cfg["fetched_models"]) < original_len:
                        removed_count += (original_len - len(cfg["fetched_models"]))
                        state_manager.db.save_provider(cfg)
                
                st.toast(f"✅ 已成功移除 {removed_count} 个无效模型！", icon="🧹")
                # Clear results to hide button
                st.session_state.model_test_results = {}
                st.rerun()

    for p_idx, config in enumerate(st.session_state.llm_configs):
        # Skip OpenRouter in Prep Pool (Shown in Tab 1)
        if config.get("name") == "OpenRouter" or "openrouter.ai" in config.get("base_url", ""):
            continue

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
        h1, h2, h3, h_lat, h4 = st.columns([1, 4, 3, 1.5, 1])
        h1.write("**状态**")
        h2.write("**模型名称**")
        h3.write("**特性标签**")
        h_lat.write("**响应 (ms)**")
        h4.write("**收藏**")
        st.divider()

        for row in all_rows:
            c1, c2, c3, c_lat, c4 = st.columns([1, 4, 3, 1.5, 1])
            
            with c1:
                st.markdown(row["Logo"], unsafe_allow_html=True)
                
            with c2:
                st.write(f"**{row['Model ID']}**")
                st.caption(row["Provider"])
                
            with c3:
                # Render tags as badges
                tags_html = "".join([f'<span style="background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); padding:2px 8px; border-radius:12px; font-size:0.75em; margin-right:4px; color:#ccc;">{t}</span>' for t in row["Tags"]])
                st.markdown(tags_html, unsafe_allow_html=True)
            
            with c_lat:
                lat = st.session_state.model_test_results.get(row["Model ID"])
                if lat is not None:
                    if lat < 0:
                        st.caption("❌ Error")
                    else:
                        color = "#4CAF50" if lat < 1000 else "#FFC107" if lat < 3000 else "#F44336"
                        st.markdown(f"<span style='color:{color}; font-weight:bold'>{int(lat)}ms</span>", unsafe_allow_html=True)
                else:
                    st.caption("-")

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
