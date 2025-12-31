import pytest
import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_init_endpoint():
    # 1. Prepare valid payload matching the new schema
    payload = {
        "script": [
            {
                "timeline": "Morning",
                "event": "Breakfast",
                "characters": "Alice; Bob",
                "description": "Eating breakfast",
                "location": "Kitchen",
                "goal": "Eat",
                "max_turns": 5
            }
        ],
        "actors": [
            {
                "name": "Alice",
                "llm_config": {
                    "api_key": "test",
                    "base_url": "http://test",
                    "model": "gpt-4"
                },
                "system_prompt": "You are Alice",
                "memory": "I like toast"
            }
        ],
        "world_bible": {"theme": "Daily Life"},
        "stage_type": "聊天群聊"
    }

    try:
        # 2. Send POST request (disable proxies)
        session = requests.Session()
        session.trust_env = False
        resp = session.post(f"{BASE_URL}/init", json=payload, timeout=5)
        
        # 3. Assertions
        assert resp.status_code == 200, f"Init failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"
        
        print("\n✅ Init Endpoint returned 200 OK")

        # 4. Verify Side Effects (Status Endpoint)
        time.sleep(1) # Wait for async db write if any (though init is sync mostly)
        status_resp = session.get(f"{BASE_URL}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        assert status_data["total_events"] == 1
        assert status_data["world_bible"]["theme"] == "Daily Life"
        
        print("✅ Status Endpoint verified persistence")

    except requests.exceptions.ConnectionError:
        pytest.fail("Could not connect to chat_server. Make sure it is running on port 8001.")
