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
        Delegates to prompt_templates for centralized management.
        """
        from core.utils.prompt_templates import get_stage_directives
        
        context = {
            "nickname": nickname,
            "group_name": group_name,
            "members": all_members_str
        }
        return get_stage_directives(self._stageType, context)
