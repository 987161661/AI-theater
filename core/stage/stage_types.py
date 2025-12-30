from enum import Enum

class StageType(Enum):
    CHAT_GROUP = "聊天群聊"
    TRPG = "跑团桌"
    FORUM = "网站论坛"
    COURT = "审判法庭"
    DEBATE = "辩论赛"
    GAME = "博弈游戏"
    MAZE = "传话筒迷宫"

    @classmethod
    def list_values(cls):
        return [item.value for item in cls]
