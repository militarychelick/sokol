"""
Privacy - Memory privacy controls
"""

from typing import Any


class Privacy:
    """Privacy controls for memory."""
    
    def __init__(self, store: Any) -> None:
        self.store = store
    
    async def clear_all(self) -> None:
        """Clear all memory data."""
        await self.store.clear_session()
        # Note: profile and habits are not cleared by default
    
    async def clear_session(self) -> None:
        """Clear only session memory."""
        await self.store.clear_session()
    
    async def export(self) -> dict[str, Any]:
        """Export all memory data."""
        return {
            "profile": await self.store.get_all_profile(),
            "habits": await self.store.get_habits(),
            "session": await self.store.get_session_memory(),
        }
    
    async def delete_habits(self, pattern_type: str) -> None:
        """Delete habits of a specific type."""
        # Implementation depends on store
        pass
