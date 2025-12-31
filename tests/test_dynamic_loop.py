
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from chat_server import StageManager, ScriptEvent, ActorConfig, InitRequest

@pytest.mark.asyncio
async def test_dynamic_loop_convergence():
    # Setup
    manager = StageManager()
    
    # Mock LLM Clients
    mock_client = MagicMock()
    # Return a mocked response structure
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Doing stuff [SCENE_END]"))]
    
    # Mock the client.chat.completions.create to return mock_response
    mock_client.client.chat.completions.create.return_value = mock_response
    mock_client.model_name = "mock-model"
    
    # Initialize with 1 actor and 1 event
    actor = ActorConfig(name="Alice", llm_config={"api_key":"x","base_url":"x","model":"x"}, system_prompt="You are Alice")
    manager.actors = {"Alice": actor}
    manager.llm_clients = {"Alice": mock_client}
    manager.actor_memories = {"Alice": MagicMock()} # simple mock
    # Mock MemoryBank methods called
    manager.actor_memories["Alice"].get_full_memory_prompt.return_value = "Memory"
    
    event = ScriptEvent(
        timeline="Day 1", 
        event="Test Event", 
        characters="Alice", 
        description="Testing loop", 
        location="Lab", 
        goal="Converge",
        max_turns=3
    )
    
    # Mock broadcast to avoid network errors
    manager.broadcast = AsyncMock()
    manager.is_playing = True
    
    # Run _handle_event_step
    # It should call LLM, get "[SCENE_END]", and break.
    
    # Also mock _invoke_director_adaptation to see if it gets called
    manager._invoke_director_adaptation = AsyncMock()
    
    await manager._handle_event_step(event)
    
    # Verification
    # 1. Did it broadcast dialogue?
    validation = any(c[0][0]['type'] == 'dialogue' and "Doing stuff" in c[0][0]['content'] for c in manager.broadcast.call_args_list)
    assert validation, "Dialogue should be broadcasted"
    
    # 2. Did it broadcast scene end signal?
    validation_end = any(c[0][0]['type'] == 'stage_direction' and "发起了场景结束信号" in c[0][0]['content'] for c in manager.broadcast.call_args_list)
    assert validation_end, "Scene end signal should be broadcasted"
    
    # 3. Did it invoke director adaptation?
    manager._invoke_director_adaptation.assert_called_once()


@pytest.mark.asyncio
async def test_director_adaptation_trigger():
    manager = StageManager()
    manager.script = [
        ScriptEvent(timeline="T1", event="E1", characters="A", description="D1", location="L", goal="G1"),
        ScriptEvent(timeline="T2", event="E2", characters="A", description="D2", location="L", goal="G2 (Original)")
    ]
    manager.current_index = 0
    manager.llm_clients = {"Director": MagicMock()} # Mock director client
    manager.broadcast = AsyncMock()
    manager.world_bible = {"theme": "Test Theme"}
    
    # Mock ScriptGenerator
    with patch("chat_server.ScriptGenerator") as MockGen:
        instance = MockGen.return_value
        # adapt_script returns a new plan
        instance.adapt_script.return_value = {
            "Time": "T2-Adapted",
            "Event": "E2-Adapted",
            "Goal": "G2-Adapted"
        }
        
        await manager._invoke_director_adaptation(manager.script[0], "Summary of E1")
        
        # Verify ScriptGenerator was called
        instance.adapt_script.assert_called_once()
        
        # Verify script was updated
        updated_event = manager.script[1]
        assert updated_event.goal == "G2-Adapted"
        assert updated_event.event == "E2-Adapted"
        assert updated_event.timeline == "T2-Adapted"
