"""
Session memory - Short-term memory for current session
"""

from typing import Any


class SessionMemory:
    """Short-term memory for current session."""
    
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self._interactions: list[dict[str, Any]] = []
    
    def add(self, interaction: dict[str, Any]) -> None:
        """Add interaction to session memory."""
        self._interactions.append(interaction)
        
        # Enforce limit
        if len(self._interactions) > self.limit:
            self._interactions = self._interactions[-self.limit:]
    
    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent interactions."""
        return self._interactions[-count:]
    
    def get_context(self) -> str:
        """Get context string for LLM."""
        recent = self.get_recent(5)
        
        if not recent:
            return "No recent context."
        
        context_lines = []
        for i, interaction in enumerate(recent, 1):
            context_lines.append(f"{i}. User: {interaction.get('input', '')}")
            context_lines.append(f"   Action: {interaction.get('action', '')}")
            context_lines.append(f"   Result: {interaction.get('result', '')}")
        
        return "\n".join(context_lines)
    
    def clear(self) -> None:
        """Clear session memory."""
        self._interactions.clear()
