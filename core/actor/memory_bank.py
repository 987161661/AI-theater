from typing import List, Dict, Optional

class MemoryBank:
    """
    Manages structured memories for a specific actor.
    Distinguishes between 'Core Persona' (Secrets), 'Sliding Window' (Short-term),
    and 'Projected Facts' (Long-term).
    """
    def __init__(self, actor_name: str, initial_memories: Optional[List[str]] = None):
        self.actor_name = actor_name
        self._secrets: List[str] = initial_memories or []
        self._short_term: List[str] = []
        self._long_term: List[str] = []
        self._max_short_term = 10

    def add_short_term(self, content: str):
        """Adds a recent interaction to short-term memory."""
        self._short_term.append(content)
        if len(self._short_term) > self._max_short_term:
            self._short_term.pop(0)

    def add_long_term(self, content: str):
        """Adds a consolidated/reflected memory (e.g., Scene Summary)."""
        self._long_term.append(content)

    def add(self, content: str):
        """Alias for add_short_term (Compatibility)."""
        self.add_short_term(content)

    def get_recent(self, limit: int = 5) -> str:
        """Returns the last N short-term memories as a formatted string."""
        recent = self._short_term[-limit:]
        if not recent:
            return "暂无近期记忆。"
        return "\n".join([f"- {m}" for m in recent])


    def add_secret(self, secret: str):
        """Permanent core knowledge/motivations."""
        if secret not in self._secrets:
            self._secrets.append(secret)

    def get_full_memory_prompt(self) -> str:
        """Constructs a consolidated memory prompt."""
        sections = []
        
        if self._secrets:
            sections.append("【核心秘密/动机】")
            sections.extend([f"- {s}" for s in self._secrets])
            
        if self._long_term:
            sections.append("\n【长期记忆/往事 (Long-term)】")
            sections.extend([f"- {m}" for m in self._long_term[-5:]])

        if self._short_term:
            sections.append("\n【近期记忆 (Short-term)】")
            sections.extend([f"- {m}" for m in self._short_term])
            
        return "\n".join(sections) if sections else "暂无记忆。"

    def serialize(self) -> Dict:
        return {
            "secrets": self._secrets,
            "short_term": self._short_term,
            "long_term": self._long_term
        }
