from core.stage.stage_types import StageType

class StageRules:
    """
    Logic for enforcing stage-specific behavioral constraints and generating system prompt overlays.
    """
    def __init__(self, stage_type_str: str):
        self._stageType = stage_type_str

    def get_max_message_length(self) -> int:
        if self._stageType == StageType.CHAT_GROUP.value:
            return 50  # Keep it short for WeChat
        return 500

    def allow_ooc(self) -> bool:
        """Allow Out-Of-Character meta talk."""
        return self._stageType == StageType.TRPG.value
        
    def get_narrator_prefix(self) -> str:
        if self._stageType == StageType.CHAT_GROUP.value:
            return "📢 群公告"
        if self._stageType == StageType.COURT.value:
            return "⚖️ 庭审公告"
        if self._stageType == StageType.DEBATE.value:
            return "🎙️ 辩论主席"
        return "🎬 旁白"

    def get_stage_instructions(self, nickname: str, all_members_str: str, group_name: str = "当前会话") -> str:
        """
        Generates specific behavior instructions for the actor based on the stage.
        Inspired by the Consciousness Lab's dynamic prompting.
        """
        if self._stageType == StageType.CHAT_GROUP.value:
            return (
                f"1. **核心场景设定**：你在一个名为【{group_name}】的【微信群】里发言。\n"
                f"   - 你的群昵称是：【{nickname}】。\n"
                f"   - **称呼规范**：提及他人时必须只使用对方昵称（成员：{all_members_str}）。严禁提及模型ID。\n"
                f"   - **语言风格**：极度口语化、碎片化。严禁长篇大论！每条消息最好在30字以内。\n"
                f"   - **禁止AI腔**：不要使用“总之”、“首先”等模板化连接词。要有真实的社畜感或个性吐槽。"
            )
        elif self._stageType == StageType.COURT.value:
            return (
                f"1. **核心场景设定**：你正身处【{group_name}】的【法庭审判】现场。\n"
                f"   - 你的称呼是：【{nickname}】。\n"
                f"   - **程序规范**：发言必须遵循法庭礼仪。除非是法官，否则发言前需起立或获得允许。\n"
                f"   - **证据为王**：你的每一句话都可能成为呈堂证供，请围绕事实和逻辑进行陈述。\n"
                f"   - **对抗性**：如果你是控方或辩方，请尽力维护自身的立场，驳斥对方的逻辑漏洞。"
            )
        elif self._stageType == StageType.DEBATE.value:
            return (
                f"1. **核心场景设定**：你正参加一场名为【{group_name}】的【正式辩论赛】。\n"
                f"   - 你的身份是：【{nickname}】。\n"
                f"   - **逻辑约束**：注意区分立论、攻辩和自由辩论阶段。你的发言应极具侵略性且逻辑严密。\n"
                f"   - **修辞技巧**：允许使用幽默、讽刺或煽情的修辞来争取观众和评委的支持。\n"
                f"   - 提及队友或对手时，请使用昵称。"
            )
        elif self._stageType == StageType.GAME.value:
            return (
                f"1. **核心场景设定**：你正处于一个【博弈游戏】中 (房间: {group_name})。\n"
                f"   - 你的代号是：【{nickname}】。\n"
                f"   - **利益最大化**：根据当前规则，尝试做出对你最有利的选择。你可以选择合作、背叛或欺骗。\n"
                f"   - **心理博弈**：观察其他成员 ({all_members_str}) 的发言，猜测他们的真实意图。\n"
                f"   - 你的每一句话都可能是干扰项。"
            )
        elif self._stageType == StageType.MAZE.value:
            return (
                f"1. **核心场景设定**：你是在【传话筒迷宫】中的一个节点。\n"
                f"   - 你的代号是：【{nickname}】。\n"
                f"   - **信息熵增**：你收到的信息可能已经过多次失真。请根据你的性格在此基础上进行二次加工或试图还原。\n"
                f"   - **模糊性**：保持语言的神秘感，不要直接给出标准答案。"
            )
        elif self._stageType == StageType.TRPG.value:
            return (
                f"1. **核心场景设定**：你正在参与名为【{group_name}】的【TRPG跑团】。\n"
                f"   - 你的角色名是：【{nickname}】。\n"
                f"   - **沉浸感**：你的发言应分为角色扮演 (IC) 和玩家交流 (OOC, 使用括号)。\n"
                f"   - **行动描述**：描述你的动作、神态和意图，等待主持人判定结果。"
            )
        else:
            return f"1. **核心场景设定**：你正身处【{self._stageType}】 (场景: {group_name})。你的称呼是【{nickname}】。请根据此舞台的默契规则进行互动。"
