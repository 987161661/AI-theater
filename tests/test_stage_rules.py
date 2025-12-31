import pytest
from core.stage.stage_rules import StageRules
from core.stage.stage_types import StageType

def test_stage_instructions_chat_group():
    rules = StageRules(StageType.CHAT_GROUP.value)
    instr = rules.get_stage_instructions("Alice", "Alice、Bob", "DeepMind Group")
    assert "微信群" in instr
    assert "Alice" in instr
    assert "DeepMind Group" in instr
    assert "Alice、Bob" in instr
    assert "[拍一拍 @昵称]" in instr
    assert "[表情包:" in instr
    assert "[发红包:" in instr
    assert "碎片化输出" in instr
    assert "Few-Shot Examples" in instr
    assert "Good" in instr

def test_stage_instructions_court():
    rules = StageRules(StageType.COURT.value)
    instr = rules.get_stage_instructions("Judge", "Judge、Defense", "The Great Trial")
    assert "法庭审理现场" in instr  # Updated string
    assert "Judge" in instr
    assert "程序规范" not in instr # "程序规范" was removed or changed to "语境" / "行为" logic
    assert "遵守法庭礼仪" in instr

def test_narrator_prefix():
    rules = StageRules(StageType.DEBATE.value)
    assert rules.get_narrator_prefix() == "🎙️ 辩论主席"
    
    rules = StageRules(StageType.CHAT_GROUP.value)
    assert rules.get_narrator_prefix() == "📢 群公告"
