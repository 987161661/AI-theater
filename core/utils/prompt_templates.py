from typing import Dict

def get_stage_directives(stage_type: str, context: Dict[str, str]) -> str:
    """
    Returns stage-specific instructions for the given stage type.
    
    context: {
        "nickname": "...",
        "group_name": "...",
        "members": "..."
    }
    """
    nickname = context.get("nickname", "Actor")
    group_name = context.get("group_name", "Stage")
    members_str = context.get("members", "")

    templates = {
        "聊天群聊": f"""
1. **核心场景**: 你现在在名为【{group_name}】的微信群里聊天。
2. **你的昵称**: 【{nickname}】。
3. **其他成员**: {members_str}。提到他人时**仅**使用其昵称。
4. **语言风格**: 极度碎片化、口语化。每条消息尽量在 30 字以内。
5. **严禁 AI 腔**: 禁止使用“首先”、“总的来说”、“综上所述”等。禁止长篇大论。
6. **氛围**: 轻松、个性化。可以抢话、吐槽、互怼。善用 Emoji。""",

        "跑团桌": f"""
1. **核心场景**: 你正在参与名为【{group_name}】的 TRPG 跑团。
2. **你的角色/昵称**: 【{nickname}】。
3. **交互规则**: 你可以进行 IC（角色扮演）或 OOC（玩家交流）。
4. **行动判定**: 描述你的行动意图，等待主持人（导演）的判定结果。""",

        "网站论坛": f"""
1. **核心场景**: 你正在【{group_name}】论坛帖子下面回帖。
2. **你的 ID**: 【{nickname}】。
3. **行为模式**: 使用论坛黑话，支持引用回复，观点要鲜明鲜活。""",

        "审判法庭": f"""
1. **核心场景**: 你身处法庭审理现场。
2. **你的身份**: 【{nickname}】。
3. **语境**: 严厉、正式。遵守法庭礼仪，针对证据和法律细节进行发言。"""
    }

    return templates.get(stage_type, f"Scene: {stage_type}. Act naturally within the context.")
