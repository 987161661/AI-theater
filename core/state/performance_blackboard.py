import logging
from typing import List, Dict, Set

logger = logging.getLogger("Blackboard")

class PerformanceBlackboard:
    """
    A centralized 'Blackboard' for storing global facts and state changes.
    All actors can see these facts to ensure narrative consistency.
    """
    def __init__(self):
        self._facts: List[Dict[str, str]] = [] # List of {fact, timestamp, category}
        self._locked_facts: Set[str] = set()    # Facts that cannot be changed (Canon)

    def add_fact(self, fact: str, category: str = "general"):
        """Adds a new fact to the blackboard."""
        if fact not in [f["fact"] for f in self._facts]:
            self._facts.append({
                "fact": fact,
                "category": category
            })
            logger.info(f"New Fact Added: [{category}] {fact}")

    def get_all_facts(self) -> str:
        """Returns a string representation of all facts for prompt injection."""
        if not self._facts:
            return "目前尚无记录的全局事实。"
        
        lines = []
        for i, f in enumerate(self._facts, 1):
            lines.append(f"{i}. [{f['category'].upper()}] {f['fact']}")
        return "\n".join(lines)

    def clear(self):
        self._facts = []
        self._locked_facts = set()
