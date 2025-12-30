# AI Theater 项目架构解析

## 1. 核心逻辑概述 (Core Logic)

AI Theater 是一个基于多智能体协作的交互式演艺平台。其核心逻辑模仿真实剧院的运作流程，分为 **编剧 (Scripting)**、**选角 (Casting)**、**舞台架构 (World Building)** 和 **实时表演 (Live Performance)** 四个阶段。

- **导演 (Director)**: 负责顶层逻辑。它不仅生成剧本大纲，还定义了剧本发生的“世界观”（World Bible），并根据剧本需求自动进行角色分配和特征提取。
- **演员 (Actor)**: 每个演员都是一个独立的 LLM 实例。他们拥有独特的 **人格 (Persona)** 和 **私有记忆 (Private Memory)**。在表演中，他们需要遵循舞台规则并对环境事件做出响应。
- **舞台 (Stage)**: 是表演发生的容器。它定义了交互的范式（如：群聊模式、辩论模式、TRPG 模式）。舞台负责维护表演状态，并通过 WebSocket 实现模型与 UI 的实时同步。
- **上帝模式 (God Controller)**: 允许用户实时干预表演过程，包括暂停/恢复、剧情跳跃、突发事件注入等。

## 2. 数据流向 (Data Flow)

整个项目的数据流动可以概括为：**配置驱动 -> 动态生成 -> 实时联动**。

1.  **初始化阶段**:
    *   用户输入主题 -> `ScriptGenerator` 生成结构化剧本 (DataFrame)。
    *   `WorldBuilder` 根据剧本和主题构建“世界观手册” (World Bible)。
    *   `CastingLogic` 分析剧本角色，从演员池中选角或生成新角色。
2.  **启动阶段**:
    *   `PersonaFactory` 为每个角色生成详细的 System Prompt（包含性格、私有记忆、舞台约束）。
    *   UI 调用后台 `/init` 接口，将剧本、演员配置和世界观同步至 `StageManager`。
3.  **表演阶段 (WebSocket)**:
    *   `StageManager` 开启主循环，按剧本时间轴广播事件。
    *   相关演员收到事件 -> 连接对应模型接口 -> 生成符合角色的回复 -> 广播至 UI 渲染。
    *   用户通过 `God Controller` 发送控制命令，动态修改 `StageManager` 的运行状态。

## 3. 关键文件路径 (Key File Paths)

| 路径 | 描述 |
| :--- | :--- |
| `app.py` | 项目主要入口点（Streamlit 服务）。 |
| `chat_server.py` | 核心后端，基于 FastAPI 实现的 WebSocket 实时舞台服务器，包含 `StageManager`。 |
| `core/director.py` | 导演模块外观 (Facade)，整合剧本生成、选角和世界观构建。 |
| `core/actor.py` | 选角导演与演员基础逻辑入口。 |
| `core/llm_provider.py` | 统一的 LLM 调用接口封装，支持多种 Provider。 |
| `core/stage/stage_rules.py` | 舞台规则定义，包含不同场景下的系统指令注入逻辑。 |
| `components/director_panel.py` | UI 组件：导演控制面板，负责剧本与选角的交互。 |
| `pages/1_AI_Theater.py` | UI 主页面：AI 剧场表演大厅。 |

## 4. 架构原则 (Architecture Principles)

- **UI 与业务逻辑分离**: 所有的状态流转（剧本索引、播放状态）由 `chat_server.py` 的 `StageManager` 维护，Streamlit 仅作为状态的反映者和指令的发送者。
- **模块化解耦**: 导演的功能被拆分为 `ScriptGenerator` (生成器)、`CastingLogic` (选角)、`WorldBuilder` (世界观) 和 `DirectorChat` (咨询)，由 `Director` Facade 统一暴露。
- **接口驱动**: 不同的舞台模式通过 `stage_rules.py` 进行扩展，而无需修改核心调度逻辑。
