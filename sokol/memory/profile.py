"""
User profile - Persistent user preferences
"""

from typing import Any


class UserProfile:
    """User profile with preferences and settings."""
    
    def __init__(self, store: Any) -> None:
        self.store = store
        self._cache: dict[str, str] = {}
    
    async def load(self) -> None:
        """Load profile from store."""
        self._cache = await self.store.get_all_profile()
    
    async def save(self, key: str, value: str) -> None:
        """Save profile value."""
        self._cache[key] = value
        await self.store.set_profile(key, value)
    
    def get(self, key: str, default: str | None = None) -> str | None:
        """Get profile value from cache."""
        return self._cache.get(key, default)
    
    def set(self, key: str, value: str) -> None:
        """Set profile value in cache (async save required)."""
        self._cache[key] = value
    
    def get_all(self) -> dict[str, str]:
        """Get all profile values."""
        return self._cache.copy()
    
    async def persist(self) -> None:
        """Persist all cached values to store."""
        for key, value in self._cache.items():
            await self.store.set_profile(key, value)
