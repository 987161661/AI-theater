import requests
from openai import OpenAI
import json

def test_api(name, base_url, api_key):
    print(f"\n--- Testing {name} ---")
    print(f"Base URL: {base_url}")
    
    # 1. Test /models endpoint manually
    try:
        print("1. Fetching models list...")
        resp = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            print("Models success!")
            data = resp.json()
            ids = [m['id'] for m in data.get('data', [])]
            print(f"Found {len(ids)} models: {ids}")
        else:
            print(f"Models failed: {resp.text}")
    except Exception as e:
        print(f"Models error: {e}")

    # 2. Test chat completion with a few common model names
    client = OpenAI(api_key=api_key, base_url=base_url)
    models_to_try = ["mimo-v2-flash", "mimo-v1", "gpt-3.5-turbo", "default"]
    
    print("\n2. Testing Chat Completion...")
    for model in models_to_try:
        try:
            print(f"Trying model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            print(f"SUCCESS with {model}: {response.choices[0].message.content}")
            break
        except Exception as e:
            print(f"FAILED with {model}: {e}")

if __name__ == "__main__":
    key = "sk-sqjv6obz83nma1wx8tntb8j1skejlo8cyyrle47hemnwn1m7"
    
    # Test both Xiaomi endpoints
    test_api("Xiaomi MiLM", "https://api.ai.mi.com/v1", key)
    test_api("Xiaomi MiMo", "https://api.xiaomimimo.com/v1", key)
