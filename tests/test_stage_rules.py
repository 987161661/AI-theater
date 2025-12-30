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

def test_stage_instructions_court():
    rules = StageRules(StageType.COURT.value)
    instr = rules.get_stage_instructions("Judge", "Judge、Defense", "The Great Trial")
    assert "法庭审判" in instr
    assert "Judge" in instr
    assert "程序规范" in instr

def test_narrator_prefix():
    rules = StageRules(StageType.DEBATE.value)
    assert rules.get_narrator_prefix() == "🎙️ 辩论主席"
    
    rules = StageRules(StageType.CHAT_GROUP.value)
    assert rules.get_narrator_prefix() == "📢 群公告"
