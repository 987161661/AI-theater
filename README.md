# 🎭 AI Theater (AI 剧场)

> **让 AI 演员在您的指挥下，上演一场场扣人心弦的交互式戏剧。**

AI Theater 是一个集成了多智能体协作、自动化创作与动态表演的交互式剧场系统。它不仅是一个创作工具，更是一个探索 AI 意识、情感共鸣与叙事逻辑的实验场。

---

## ✨ 核心特性

- **🎬 智能导演系统 (AI Director)**: 
  - **剧本生成**: 基于约束的自动化剧本创作。
  - **选角逻辑**: 自动生成角色人设、个人记忆与系统提示词。
  - **世界观构建**: 自动生成深度关联的世界指南 (World Bible)。
- **🎭 交互式表演区域 (Theater)**:
  - **多角色演绎**: 支持多个 AI 演员基于角色设定进行实时对话。
  - **上帝视角控制**: 导演可进行实时干预、暂停、时间轴跳跃或事件注入。
  - **多种舞台模式**: 辩论、法庭、博弈论、剧本杀等多样化表演规则。
- **📺 沉浸式观影 (Showcase)**: 
  - 仿微信桌面端的高保真交互界面，提供流畅、真实的动态观演体验。
- **⚙️ 灵活配置**: 支持主流 LLM 服务商（OpenAI, DeepSeek, Claude 等），支持本地或模型列表自动获取。

---

## 🚀 快速开始

### 1. 环境准备

确保您的系统已安装 **Python 3.9+**。

```bash
# 克隆项目
git clone https://github.com/987161661/AI-theater.git
cd AI-theater

# 创建并激活虚拟环境 (可选但推荐)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

1. 启动项目：
   ```bash
   streamlit run app.py
   ```
2. 在侧边栏选择 **⚙️ Config**。
3. 添加您的模型服务商（如 OpenAI 或兼容接口）及其 API Key。
4. 保存配置。

### 3. 开始演出

1. 在侧边栏进入 **🎬 AI Theater**。
2. 配置导演设定，生成剧本与角色。
3. 点击“开始表演”，在 **📺 Showcase** 或表演区域观看 AI 演员的演出。

---

## 🛠️ 技术栈

- **Frontend**: Streamlit (核心 UI), Vanilla CSS (UI 优化)
- **Backend**: FastAPI (WebSocket 服务)
- **AI Core**: OpenAI Python SDK, 多智能体协作框架
- **Data**: SQLite (持久化存储), Pandas
- **Visualization**: Plotly

---

## 🤝 贡献与反馈

如果您有任何想法、建议或发现了 Bug，欢迎提交 Issue 或 Pull Request。

---

*Created with ❤️ by Antigravity*
