import json
import re
from typing import Any, Dict, Optional

def repair_json(json_str: str) -> str:
    """
    Attempts to fix common malformed JSON issues from LLMs.
    1. Balances braces.
    2. Closes unclosed strings.
    """
    json_str = json_str.strip()
    
    # Simple unclosed string fix
    if json_str.count('"') % 2 != 0:
        json_str += '"'
        
    # Balanced braces fix
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        
    return json_str

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts and parses JSON from text that might contain markdown or fluff.
    """
    # Try markdown block first
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            repaired = repair_json(json_match.group(1))
            try:
                return json.loads(repaired)
            except:
                pass

    # Try finding the first '{' and last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        potential_json = text[start_idx:end_idx + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            repaired = repair_json(potential_json)
            try:
                return json.loads(repaired)
            except:
                pass
                
    return None
