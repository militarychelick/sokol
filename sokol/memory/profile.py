"""
User profile - Personalization per user
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config


class UserProfile:
    """User profile for personalization."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._profile: dict[str, Any] = {}
    
    async def load(self) -> None:
        """Load user profile."""
        # TODO: Load from database
        self._profile = {
            "language": "ru",
            "name": "User",
            "preferences": {},
        }
    
    async def save(self) -> None:
        """Save user profile."""
        # TODO: Save to database
        pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get profile value."""
        return self._profile.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set profile value."""
        self._profile[key] = value
