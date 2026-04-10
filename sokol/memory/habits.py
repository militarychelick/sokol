"""
Habits - Behavioral pattern tracking
"""

from typing import Any


class Habits:
    """Track and learn user behavioral patterns."""
    
    def __init__(self, store: Any, min_frequency: int = 3) -> None:
        self.store = store
        self.min_frequency = min_frequency
    
    async def record(self, pattern_type: str, pattern_data: str) -> None:
        """Record a behavioral pattern."""
        await self.store.increment_habit(pattern_type, pattern_data)
    
    async def get_patterns(self, pattern_type: str | None = None) -> list[dict[str, Any]]:
        """Get patterns above frequency threshold."""
        all_habits = await self.store.get_habits(pattern_type)
        
        return [
            habit
            for habit in all_habits
            if habit["frequency"] >= self.min_frequency
        ]
    
    async def get_suggestions(self, context: str) -> list[str]:
        """Get suggestions based on habits."""
        # Simple implementation - return top patterns
        patterns = await self.get_patterns()
        
        suggestions = []
        for pattern in patterns[:5]:
            suggestions.append(pattern["pattern_data"])
        
        return suggestions
