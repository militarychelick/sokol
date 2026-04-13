"""Memory manager - coordinates all memory stores."""

from datetime import datetime
from pathlib import Path
from typing import Any

from sokol.core.config import get_config
from sokol.core.types import UserProfile
from sokol.observability.logging import get_logger
from sokol.memory.session import SessionMemory, SessionMemoryModel
from sokol.memory.profile import ProfileMemory
from sokol.memory.longterm import LongTermMemory, LongTermMemoryModel

logger = get_logger("sokol.memory.manager")


class MemoryManager:
    """
    Central memory manager.

    Coordinates:
    - Session memory (current conversation)
    - Profile memory (user preferences)
    - Long-term memory (patterns)
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        config = get_config()
        self._data_dir = data_dir or Path(config.memory.profile_path).parent
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize stores
        self._session = SessionMemory(self._data_dir / "session.db")
        self._profile = ProfileMemory(config.memory.profile_path)
        self._longterm = LongTermMemory(config.memory.longterm_path)

        # Current session
        self._current_session: SessionMemoryModel | None = None
        self._current_profile: UserProfile | None = None

        logger.info_data(
            "Memory manager initialized",
            {"data_dir": str(self._data_dir)},
        )

    @property
    def session(self) -> SessionMemory:
        """Session memory store."""
        return self._session

    @property
    def profile(self) -> ProfileMemory:
        """Profile memory store."""
        return self._profile

    @property
    def longterm(self) -> LongTermMemory:
        """Long-term memory store."""
        return self._longterm

    @property
    def current_session(self) -> SessionMemoryModel | None:
        """Current active session."""
        return self._current_session

    @property
    def current_profile(self) -> UserProfile | None:
        """Current active profile."""
        return self._current_profile

    def start_session(self) -> SessionMemoryModel:
        """Start a new session."""
        self._current_session = self._session.create_session()
        logger.info("Session started")
        return self._current_session

    def load_profile(self, profile_id: str | None = None) -> UserProfile:
        """Load profile (default if not specified)."""
        if profile_id:
            profile = self._profile.get(profile_id)
            if not profile:
                raise ValueError(f"Profile not found: {profile_id}")
        else:
            profile = self._profile.get_default_profile()

        self._current_profile = profile
        logger.info_data("Profile loaded", {"profile_id": profile.id, "name": profile.name})
        return profile

    def add_message(self, role: str, content: str) -> bool:
        """Add message to current session."""
        if not self._current_session:
            self.start_session()

        return self._session.add_conversation_entry(
            self._current_session.id,
            role,
            content,
        )

    def get_conversation_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get conversation history from current session."""
        if not self._current_session:
            return []

        entries = self._session.get_conversation(self._current_session.id, limit)
        return [
            {"role": e.role, "content": e.content, "timestamp": e.timestamp}
            for e in entries
        ]

    def get_recent_interactions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent interactions for UI display."""
        try:
            if not self._current_session:
                return []

            entries = self._session.get_conversation(self._current_session.id, limit)
            if not entries:
                return []
            
            # Convert to format expected by UI: timestamp, source, input_text, response_text
            interactions = []
            for i in range(0, len(entries), 2):  # Process pairs (user/assistant)
                if i + 1 < len(entries):
                    user_entry = entries[i]
                    assistant_entry = entries[i + 1]
                    if user_entry.role == "user" and assistant_entry.role == "assistant":
                        interactions.append({
                            "timestamp": user_entry.timestamp,
                            "source": "user",
                            "input_text": user_entry.content,
                            "response_text": assistant_entry.content
                        })
            return interactions
        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []

    def set_context(self, key: str, value: Any) -> bool:
        """Set context in current session."""
        if not self._current_session:
            return False
        return self._session.set_context(self._current_session.id, key, value)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context from current session."""
        if not self._current_session:
            return default
        return self._session.get_context(self._current_session.id, key) or default

    def set_preference(self, key: str, value: Any) -> bool:
        """Set preference in current profile."""
        if not self._current_profile:
            self.load_profile()
        if not self._current_profile:
            return False
        return self._profile.set_preference(self._current_profile.id, key, value)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get preference from current profile."""
        if not self._current_profile:
            self.load_profile()
        if not self._current_profile:
            return default
        return self._profile.get_preference(self._current_profile.id, key, default)

    def record_app_usage(self, app_name: str) -> bool:
        """Record app usage in profile."""
        if not self._current_profile:
            self.load_profile()
        if not self._current_profile:
            return False
        return self._profile.add_frequently_used_app(
            self._current_profile.id, app_name
        )

    def save_pattern(
        self,
        pattern_type: str,
        pattern_data: dict[str, Any],
        tags: list[str] | None = None,
    ) -> LongTermMemoryModel:
        """Save a pattern to long-term memory."""
        return self._longterm.create_pattern(pattern_type, pattern_data, tags)

    def find_patterns(self, pattern_type: str | None = None) -> list[LongTermMemoryModel]:
        """Find patterns by type or all."""
        if pattern_type:
            return self._longterm.find_by_type(pattern_type)
        return self._longterm.list_all()

    def get_frequent_patterns(self, limit: int = 10) -> list[LongTermMemoryModel]:
        """Get most frequently used patterns."""
        return self._longterm.get_most_used(limit)

    def clear_session(self) -> int:
        """Clear current session conversation."""
        if not self._current_session:
            return 0
        return self._session.clear_conversation(self._current_session.id)

    def clear_all_sessions(self) -> int:
        """Clear all sessions."""
        return self._session.clear()

    def clear_profile(self) -> bool:
        """Clear current profile preferences."""
        if not self._current_profile:
            return False
        return self._profile.update(
            self._current_profile.id,
            {"preferences": {}, "frequently_used_apps": [], "work_habits": {}},
        )

    def export_session(self) -> dict[str, Any]:
        """Export current session data."""
        if not self._current_session:
            return {}

        return {
            "session_id": self._current_session.id,
            "conversation": self.get_conversation_history(),
            "context": self._current_session.context,
            "exported_at": datetime.now().isoformat(),
        }

    def export_profile(self) -> dict[str, Any]:
        """Export current profile data."""
        if not self._current_profile:
            return {}

        return {
            "profile_id": self._current_profile.id,
            "name": self._current_profile.name,
            "preferences": self._current_profile.preferences,
            "frequently_used_apps": self._current_profile.frequently_used_apps,
            "command_templates": self._current_profile.command_templates,
            "exported_at": datetime.now().isoformat(),
        }

    def shutdown(self) -> None:
        """Shutdown memory manager."""
        self._session.close()
        self._profile.close()
        self._longterm.close()
        logger.info("Memory manager shutdown")
