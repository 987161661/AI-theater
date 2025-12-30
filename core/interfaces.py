from typing import List, Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod

class IStageManager(Protocol):
    """
    舞台管理器接口：负责表演周期的完整生命周期管理。
    """
    def initialize(self, script: List[Dict], actors: List[Dict], world_bible: Dict) -> None:
        """初始化舞台环境、剧本及演员"""
        ...

    async def start(self) -> None:
        """开启表演循环"""
        ...

    def pause(self) -> None:
        """暂停表演"""
        ...

    def jump(self, index: int) -> None:
        """跳转到特定的剧情节点"""
        ...

    async def inject_event(self, content: str) -> None:
        """上帝模式：注入突发事件"""
        ...

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """向所有连接的客户端广播消息"""
        ...


class IDirector(Protocol):
    """
    导演接口：负责创意生产与资源调度。
    """
    def generate_script(self, topic: str, constraints: Dict[str, Any]) -> Any:
        """根据主题和约束生成剧本"""
        ...

    def build_world(self, topic: str, script: Any, stage_type: str) -> Dict[str, str]:
        """构建世界观手册 (World Bible)"""
        ...

    def perform_casting(self, theme: str, characters: List[str], stage_type: str) -> List[Dict]:
        """为剧本角色分配适合的演员及其人格"""
        ...


class IActor(Protocol):
    """
    演员接口：定义了 AI 智能体在舞台上的行为标准。
    """
    @property
    def name(self) -> str:
        """返回角色名称"""
        ...

    @property
    def persona(self) -> Dict[str, Any]:
        """返回角色的详细人格定义"""
        ...

    async def act(self, event_description: str, location: str, context: Optional[List[Dict]] = None) -> str:
        """
        核心行为方法：对舞台事件做出反应并输出台词/行为。
        """
        ...

    def update_memory(self, snippet: str) -> None:
        """更新演员的私有记忆库"""
        ...


class IStageRule(Protocol):
    """
    舞台规则接口：定义了不同场景下的约束逻辑。
    """
    def get_system_instruction(self, stage_type: str) -> str:
        """获取当前舞台模式下的特定系统指令"""
        ...

    def validate_action(self, action: str) -> bool:
        """验证演员的行为是否符合当前舞台的潜规则"""
        ...
