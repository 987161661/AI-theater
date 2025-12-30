import pytest
from unittest.mock import MagicMock, patch
from core.llm_provider import LLMProvider
from core.director import Director

def test_llm_provider_init():
    provider = LLMProvider("fake_key", "fake_url", "fake_model")
    assert provider.api_key == "fake_key"
    assert provider.client is not None

def test_check_connection_fail():
    # Test with empty provider
    provider = LLMProvider("", "", "")
    res = provider.check_connection()
    assert res["status"] is False
    assert "Missing Key" in res["message"]

@patch("core.director.OpenAI")
def test_director_generate_script(mock_openai):
    # Setup mock response
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = \
        "Timeline,Event,Characters,Description,Location\n09:00,Start,Alice,Hi,Home"
    
    mock_client.chat.completions.create.return_value = mock_completion
    
    director = Director(mock_client, "gpt-4")
    # New API call with constraints
    constraints = {"genre": "Sci-Fi", "reality": "Strict", "stage": "Chat"}
    df = director.generate_script_with_constraints("test topic", constraints)
    
    assert not df.empty
    assert "Alice" in df.iloc[0]["Characters"]
    assert len(df) == 1
