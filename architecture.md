# AI Theater 项目架构解析

## 1. 系统概览 (System Overview)

**AI Theater** 是一个基于 **CrewAI 多智能体协作框架 (Multi-Agent Collaboration)** 的沉浸式交互演艺平台。其核心理念是将 LLM 拟人化为“演员”，在一个由“导演团队”定义的动态“舞台”上进行实时表演。

系统采用 **前后端分离** 的架构，通过 WebSocket 实现高频实时交互，并将“戏剧创作” (Director Phase) 与“舞台表演” (Stage Phase) 解耦，实现了从剧本生成到自动化演出的完整闭环。

### 核心特性
- **动态导演循环 (Dynamic Director Loop)**: 每一幕结束后，导演会根据上一幕的剧情走向自动调整接下来的剧本，实现真正的“即兴戏剧”。
- **RAG 知识增强**: 集成 `KnowledgeBaseManager`，允许导演和演员查询外部知识库 (".pdf", ".md") 以构建更严谨的世界观。
- **拟人化演员**: 每个演员拥有独立的 System Prompt、私有记忆库 (Memory Bank) 和短期记忆流。
- **上帝模式 (God Mode)**: 用户可随时以“强制指令”介入表演，暂停时间或注入突发事件。
- **一致性对话 (Consistnecy)**: 通过 `PerformanceBlackboard` 维护结构化的对话历史，确保 AI 演员准确识别自我与他人，避免幻觉。

---

## 2. 核心模块详解 (Core Modules)

### 2.1 导演系统 (The Director System)
**路径**: `core/director/`
导演是整个系统的“大脑”，现已全面升级为 **CrewAI Agent Teams**。通过 `Facade Pattern` 统一对外暴露接口，底层由多个专业的 Crew 协同工作。

*   **`director/__init__.py` (Director Facade)**: 统一入口，将请求路由至对应的 CrewAI 实现。
*   **`crew_script_generator.py` (Script Crew)**: 剧本创作团队。
    *   `Screenwriter`: 负责撰写初稿。
    *   `Editor`: 负责格式校验与逻辑润色。
    *   `Live Director`: 负责演出时的动态剧本调整。
*   **`crew_casting.py` (Casting Crew)**: 选角团队。
    *   `Casting Director`: 分析剧本需求，推荐角色。
    *   `Persona Psychologist`: 生成深度的角色心理侧写与 System Prompt。
    *   `Automation Specialist`: 配置自动化机器人的触发规则。
*   **`crew_world_builder.py` (World Crew)**: 世界构建团队。
    *   `World Architect`: 生成严谨的“世界观手册” (World Bible)。
*   **`crew_critic.py` (Critic Crew)**: 剧评团队。
    *   `Drama Critic`: 对剧本大纲或演出效果进行专业点评。
*   **`crew_post_scene.py` (Analysis Crew)**: 演出后分析团队。
    *   `Theater Recorder`: 客观记录事实。
    *   `Relationship Psychologist`: 分析角色关系变化。
    *   `Narrative Lead`: 生成幕后总结与后续建议。

*(Legacy Modules: `script_generator.py`, `casting_logic.py`, `world_builder.py`, `critic_agent.py`, `director_chat.py` 均已保留但不再使用)*

### 2.2 舞台系统 (The Stage System)
**路径**: `core/stage/` & `chat_server.py`
舞台是表演的容器和规则执行者。

*   **`chat_server.py` (StageManager)**: 核心后端引擎。
    *   **事件循环 (Event Loop)**: 维护全局时钟，按序推进剧本事件。
    *   **WebSocket Server**: 负责与前端建立实时连接。
    *   **Post-Scene Integration**: 每幕结束后自动调用 `CrewPostSceneAnalyst` 进行总结与反馈。
    *   **Director Adaptation Trigger**: 监听场景结束信号，触发 `Live Director` 对下一幕的重写。
*   **`stage_rules.py`**: 舞台规则策略。
*   **`stage_types.py`**: 强类型的舞台枚举定义。

### 2.3 演员系统 (The Actor System)
**路径**: `core/actor/`
演员是运行在 LLM 之上的拟人化实体，现已升级为独立的 CrewAI Agent。

*   **`crew_actor.py` (CrewActor)**: 演员 Agent。
    *   每个角色都是一个独立的 CrewAI Agent。
    *   拥有持久化的 `Goal` (真实扮演) 和 `Backstory` (System Prompt)。
    *   通过 `perform()` 方法接收包含记忆、历史、舞台指示的 `Task`，并输出结构化台词。
*   **`persona_factory.py`**: (辅助) 人设生成工厂。
*   **`memory_bank.py`**: 记忆库。
    *   **Private Memory (Secret)**: 演员初始的背景设定。
    *   **Short-term Memory**: 演出过程中的对话历史。
*   **`base_actor.py`**: (Legacy) 旧版演员基类。

### 2.4 状态与存储 (State & Storage)
**路径**: `core/state/`

*   **`manager.py` (StateManager)**: 前端状态管理。封装了 Streamlit 的 `session_state`，确保 UI 组件间的数据同步。
*   **`db_manager.py`**: 持久化层。使用 SQLite (`theater.db`) 记录：
    *   完整的剧本 (Scripts)。
    *   演出场次 (Performances) 和实时日志 (Logs)。
    *   演员快照 (Actor States)。
    *   LLM 配置 (Providers)。
*   **`performance_blackboard.py`**: 黑板模式。
    *   记录全场可见的公共事实 (`Public Facts`)，如“当前天气”、“突发新闻”。
    *   维护结构化对话历史 (`dialogue_history`)，用于构建上下文。
*   **`versioning.py`**: 处理缓存失效和版本控制，确保 UI 组件在配置更改时刷新。

### 2.5 工具与辅助 (Utils)
**路径**: `core/utils/`

*   **`json_parser.py`**: 鲁棒的 JSON 解析器，能从 LLM 不完美的输出中提取结构化数据。
*   **`prompt_templates.py`**: 集中管理各舞台类型的 System Instructions 模板。
*   **`rag_engine.py`**: 基于 Embeddings 的简易 RAG 引擎，用于从文档中检索世界观背景。

---

## 3. 关键数据流 (Data Flow)

### 3.1 筹备流程 (Pre-production)
1.  **User** 在 UI 输入主题。
2.  **Director** 生成初稿剧本 (`ScriptGenerator`)。
3.  **Director** 生成世界观 (`WorldBuilder`)。
4.  **Director** 自动选角 (`CastingLogic`) -> 生成 `ActorConfig` (Prompt + Memory)。
5.  **User** 确认配置 -> UI 调用后端 `/init` 接口。

### 3.2 演出循环 (Performance Loop)
1.  **StageManager** 广播 `Current Event` (e.g., "Event: 两人在咖啡馆争吵")。
2.  **StageManager** 确定当前发言权的演员列表。
3.  **Actor** (LLM) 接收上下文:
    *   System Prompt (人设)
    *   World Bible (RAG context)
    *   Stage Rules (当前舞台规则)
    *   Public Facts (黑板)
    *   Private Memory (个人记忆)
    *   **Structured Chat History** (明确区分 "Me" vs "Others")
4.  **Actor** 生成回复 -> **WebSocket** 广播至 UI 和 其他演员。
5.  **Termination Check**: 如果演员输出 `[SCENE_END]`，当前场景结束。

### 3.3 动态适配 (Adaptation Loop)
1.  场景结束后，**StageManager**总结本场剧情。
2.  调用 **Director (ScriptGenerator)**，传入 `(Previous Summary, Next Event Plan)`。
3.  导演修改 `Next Event` 的目标和描述，使其符合逻辑地衔接上一幕。
4.  更新剧本队列，演出继续。

---

## 4. 目录结构说明 (Directory Map)

```text
f:\AI theater\
├── app.py                      # [Entry] Web 入口 (重定向器)
├── chat_server.py              # [Backend] 核心 WebSocket 服务器 & 舞台管理器 (StageManager)
├── architecture.md             # [Doc] 架构文档 (本文档)
├── theater.db                  # [Data] SQLite 数据库 (持久化存储)
├── requirements.txt            # [Config] Python 依赖列表
├── core/                       # [Core] 核心业务逻辑
│   ├── actor/                  # -> 演员子系统
│   │   ├── crew_actor.py       # [New] CrewAI 演员 Agent
│   │   ├── base_actor.py       # [Legacy] 演员基类接口
│   │   ├── memory_bank.py      # 记忆管理 (短期/私有记忆)
│   │   └── persona_factory.py  # 人设生成工厂 (Prompt Engineering)
│   ├── director/               # -> 导演子系统 (Facade)
│   │   ├── __init__.py         # 导演入口 (Director Facade)
│   │   ├── crew_script_generator.py # [New] 剧本创作 Crew
│   │   ├── crew_casting.py     # [New] 选角 Crew
│   │   ├── crew_world_builder.py # [New] 世界观 Crew
│   │   ├── crew_post_scene.py  # [New] 演出后分析 Crew
│   │   ├── crew_critic.py      # [New] 剧评 Crew
│   │   ├── script_generator.py # [Legacy] 剧本生成
│   │   ├── casting_logic.py    # [Legacy] 选角逻辑
│   │   ├── world_builder.py    # [Legacy] 世界构建
│   │   ├── director_chat.py    # [Legacy] 导演对话
│   │   └── critic_agent.py     # [Legacy] 剧本审查
│   ├── stage/                  # -> 舞台子系统
│   │   ├── stage_rules.py      # 舞台规则逻辑 (Prompt注入/行为约束)
│   │   └── stage_types.py      # 舞台类型枚举 (Enum)
│   ├── state/                  # -> 状态与数据层
│   │   ├── manager.py          # 前端 SessionState 管理器
│   │   ├── db_manager.py       # SQLite 数据库操作封装
│   │   ├── performance_blackboard.py # 黑板模式 (公共事实/对话历史)
│   │   └── versioning.py       # 状态版本控制
│   ├── utils/                  # -> 通用工具库
│   │   ├── json_parser.py      # LLM 输出解析 (JSON/Markdown)
│   │   ├── json_utils.py       # JSON 修复与提取工具
│   │   ├── prompt_templates.py # System Prompt 模板库
│   │   └── rag_engine.py       # RAG 检索引擎
│   ├── interfaces.py           # 核心接口定义 (Protocol)
│   ├── knowledge_base.py       # 知识库管理 (ChromaDB 封装)
│   └── llm_provider.py         # LLM API 统一调用封装
├── pages/                      # [UI] Streamlit 页面
│   ├── 0_Config.py             # 全局配置页 (API Key/模型管理)
│   ├── 1_AI_Theater.py         # 主剧场页面 (导演/选角/表演)
│   └── 2_Showcase.py           # 纯净观影模式 (仅显示即时聊天)
├── components/                 # [UI] 可复用组件
│   ├── director_panel.py       # 导演控制台 (剧本生成UI)
│   ├── world_bible_panel.py    # 选角与世界观面板
│   ├── websocket_chat.py       # 核心聊天组件 (仿微信UI, WebSocket客户端)
│   └── chat_box.py             # 简易聊天显示组件
└── tests/                      # [Test] 单元测试
    ├── test_blackboard_integration.py # [New] 黑板/结构化历史/一致性测试
    ├── test_dynamic_loop.py    # 导演动态追更与剧本适配逻辑测试
    ├── test_stage_rules.py     # 舞台规则与Prompt注入测试
    ├── test_core.py            # 核心组件冒烟测试
    └── debug_xiaomi.py         # 调试脚本
├── assets/                     # [Res] 静态资源 (图片/样式表)
└── additional/                 # [Legacy/Ref] 遗留与参考代码
    ├── 2_🧠_Consciousness_Lab.py # 旧版意识实验室 (参考用)
    └── app copy.py             # 备份入口
```

## 5. 技术栈 (Tech Stack)

*   **Framework**: **CrewAI** (Multi-Agent Orchestration) - 核心智能体编排框架。
*   **LLM Gateway**: **LiteLLM** (via CrewAI) - 统一多模型接口。
*   **Frontend**: Streamlit (Python UI Framework) - 负责界面渲染与指令下发。
*   **Backend**: FastAPI (Async Web Server) - 承载 WebSocket 服务与核心循环。
*   **Concurrency**: Python `asyncio` - 处理多智能体并发思考与实时消息推送。
*   **AI Orchestration**: Native OpenAI Client (Custom Logic) - 不依赖 LangChain，自研 Prompt 流。
*   **Data Processing**: Pandas (剧本结构化), NumPy (Embeddings).
*   **Storage**: SQLite (关系型数据), ChromaDB (向量数据).
*   **Pattern**: Facade (导演), Blackboard (共享状态), Event-Driven (舞台循环), Singleton (状态管理).
