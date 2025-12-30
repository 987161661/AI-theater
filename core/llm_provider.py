import os
import time
import requests
from typing import List, Dict, Optional, Any
from openai import OpenAI
import concurrent.futures

class LLMProvider:
    """
    Manages LLM API connections and testing.
    Follows Single Responsibility Principle by focusing only on connectivity and raw execution.
    """
    
    def __init__(self, api_key: str, base_url: str, model_name: str = "default"):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.client = None
        
        # Simple validation
        if self.api_key and self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def check_connection(self) -> Dict[str, Any]:
        """
        Tests the connection by sending a minimal request.
        Returns a dict with status, latency, and message.
        """
        if not self.client:
            return {"status": False, "message": "Client not initialized (Missing Key/URL)", "latency": 0}

        start_time = time.time()
        try:
            # Use a very short prompt for connectivity check
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            latency = (time.time() - start_time) * 1000 # ms
            return {
                "status": True,
                "message": "Connection Successful",
                "latency": latency,
                "response": response.choices[0].message.content
            }
        except Exception as e:
            return {
                "status": False,
                "message": str(e),
                "latency": 0
            }

    def fetch_models(self) -> List[str]:
        """
        Fetches the list of available models from the provider.
        """
        if not self.client:
            return []
        
        try:
            model_list = self.client.models.list()
            # Extract IDs
            return [m.id for m in model_list.data]
        except Exception as e:
            # Fallback or error logging
            print(f"Failed to list models: {e}")
            return []

    @staticmethod
    def batch_test_providers(configs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Tests multiple provider configurations in parallel.
        configs: List of dicts with keys: 'name', 'api_key', 'base_url', 'model'
        """
        results = []
        
        def test_single(cfg):
            provider = LLMProvider(cfg['api_key'], cfg['base_url'], cfg['model'])
            res = provider.check_connection()
            return {
                "name": cfg['name'],
                "model": cfg['model'],
                "status": res["status"],
                "latency": res["latency"],
                "error": res["message"] if not res["status"] else None
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_cfg = {executor.submit(test_single, cfg): cfg for cfg in configs}
            for future in concurrent.futures.as_completed(future_to_cfg):
                results.append(future.result())
        
        return results
