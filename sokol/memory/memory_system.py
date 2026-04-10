"""
Memory system - Main orchestrator for memory
"""

from __future__ import annotations

from pathlib import Path

from ..core.config import MemoryConfig
from ..core.exceptions import MemoryError
from .habits import Habits
from .privacy import Privacy
from .profile import UserProfile
from .session import SessionMemory
from .store import MemoryStore


class MemorySystem:
    """
    Main memory system orchestrator.
    
    Coordinates session memory, profile, habits, and privacy.
    """
    
    def __init__(self, config: MemoryConfig) -> None:
        self.config = config
        
        # Set up database path
        data_dir = Path(__file__).parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "memory.db"
        
        # Initialize components
        self.store = MemoryStore(db_path)
        self.session = SessionMemory(config.session_limit)
        self.profile = UserProfile(self.store)
        self.habits = Habits(self.store, config.habit_min_frequency)
        self.privacy = Privacy(self.store)
    
    async def initialize(self) -> None:
        """Initialize memory system."""
        await self.store.initialize()
        await self.profile.load()
    
    async def store_interaction(
        self,
        input_text: str,
        intent: Any,
        result: Any,
    ) -> None:
        """Store an interaction."""
        # Store in session
        self.session.add({
            "input": input_text,
            "intent": str(intent.intent_type),
            "action": str(intent.action_category),
            "result": result.message,
            "success": result.success,
        })
        
        # Store in database
        await self.store.store_session(
            input_text=input_text,
            intent_type=intent.intent_type.value,
            action_taken=intent.action_category.value if intent.action_category else "unknown",
            result=result.message,
            success=result.success,
        )
        
        # Record habit
        if intent.action_category:
            await self.habits.record(
                pattern_type=intent.action_category.value,
                pattern_data=input_text,
            )
    
    async def get_context(self) -> dict[str, Any]:
        """Get context for LLM."""
        return {
            "session": self.session.get_context(),
            "profile": self.profile.get_all(),
        }
    
    async def load_profile(self) -> None:
        """Load user profile."""
        await self.profile.load()
    
    async def save_profile(self, key: str, value: str) -> None:
        """Save profile value."""
        await self.profile.save(key, value)
    
    async def get_suggestions(self, context: str) -> list[str]:
        """Get suggestions based on habits."""
        return await self.habits.get_suggestions(context)
    
    async def shutdown(self) -> None:
        """Shutdown memory system."""
        await self.store.close()
