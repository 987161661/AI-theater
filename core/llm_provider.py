import os
import time
import requests
import socket
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
            # 1. Try a minimal chat completion
            try:
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=5
                )
                latency = (time.time() - start_time) * 1000
                return {"status": True, "message": "Chat Connection Successful", "latency": latency}
            except Exception as chat_err:
                # 2. Fallback: Try listing models
                try:
                    self.client.models.list()
                    latency = (time.time() - start_time) * 1000
                    return {"status": True, "message": f"API Accessible (Chat error: {str(chat_err)[:30]}...)", "latency": latency}
                except Exception as list_err:
                    return {"status": False, "message": f"Connection Failed: {str(list_err)}", "latency": 0}
        except Exception as e:
            return {"status": False, "message": str(e), "latency": 0}

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

class LocalProviderScanner:
    """
    Scans local ports for AI providers like Ollama and LM Studio.
    """
    DEFAULT_PROBE_TIMEOUT = 0.5  # seconds

    PORT_MAP = {
        11434: {"name": "Ollama (Local)", "base_url": "http://localhost:11434/v1"},
        1234: {"name": "LM Studio (Local)", "base_url": "http://localhost:1234/v1"},
    }

    @staticmethod
    def scan_common_ports() -> List[Dict[str, Any]]:
        """
        Probes default AI provider ports on localhost.
        Returns a list of detected providers.
        """
        detected = []
        
        def check_port(port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(LocalProviderScanner.DEFAULT_PROBE_TIMEOUT)
                    result = s.connect_ex(('127.0.0.1', port))
                    if result == 0:
                        info = LocalProviderScanner.PORT_MAP[port]
                        # Verify with a quick request to see if it's responsive
                        try:
                            # Ollama version check or similar
                            # For simplicity, we just check if it accepts a basic GET
                            resp = requests.get(f"{info['base_url']}/models", timeout=0.1)
                            if resp.status_code == 200:
                                return {
                                    "name": info["name"],
                                    "base_url": info["base_url"],
                                    "api_key": "not-needed",
                                    "status": "detected"
                                }
                        except:
                            pass
                        
                        return {
                            "name": info["name"],
                            "base_url": info["base_url"],
                            "api_key": "not-needed",
                            "status": "detected" # Fallback if port is open but GET failed
                        }
            except Exception:
                pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(LocalProviderScanner.PORT_MAP)) as executor:
            futures = [executor.submit(check_port, port) for port in LocalProviderScanner.PORT_MAP]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    detected.append(res)
        
        return detected

    @staticmethod
    def run_heartbeat(configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Quickly pings all providers to update their live status.
        """
        results = []
        def probe(cfg):
            start = time.time()
            try:
                # Basic check: usually just models list is enough for heartbeat
                p = LLMProvider(cfg.get('api_key', ''), cfg.get('base_url', ''), 'heartbeat')
                # Use a lightweight check
                response = requests.get(f"{cfg['base_url']}/models", 
                                     headers={"Authorization": f"Bearer {cfg['api_key']}"},
                                     timeout=1.0)
                latency = (time.time() - start) * 1000
                return {
                    "id": cfg.get("id", cfg.get("name")),
                    "active": response.status_code == 200,
                    "latency": latency if response.status_code == 200 else 0
                }
            except:
                return {
                    "id": cfg.get("id", cfg.get("name")),
                    "active": False,
                    "latency": 0
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(probe, configs))
            
        return results
