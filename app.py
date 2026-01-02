import streamlit as st
import os

# --- Page Config MUST be the first Streamlit command ---
st.set_page_config(
    page_title="IA ITheater Entry",
    page_icon="🎭",
    layout="wide"
)

from core.utils.server_manager import ensure_backend_running

# Disable CrewAI Telemetry to prevent timeouts
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

# --- Auto-start Backend Logic ---
ensure_backend_running()

st.title("🎭 Welcome to AI Theater")

st.markdown("""
### 欢迎来到 AI 剧场

请从左侧侧边栏选择功能模块：

- **⚙️ Config**: 配置模型 API Key 与网络连接。
- **🎬 AI Theater**: 核心创作与表演区域（导演、选角、舞台）。
- **📺 Showcase**: 沉浸式观影模式。

---
*Created by Antigravity*
""")

st.sidebar.success("请选择一个页面开始。")
