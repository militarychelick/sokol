"""Memory event types and sanitizer for safe memory operations."""

from typing import Any, Literal
from dataclasses import dataclass

from sokol.observability.logging import get_logger

logger = get_logger("sokol.memory.events")


MemoryEventType = Literal["fact", "tool_result", "user_preference", "state_marker"]


@dataclass
class MemoryEvent:
    """Memory event data structure."""

    event_type: MemoryEventType
    data: dict[str, Any]
    timestamp: str | None = None


class MemoryEventSanitizer:
    """
    Sanitizer for memory events to prevent storing sensitive data.

    Rules:
    - NEVER store sensitive safety-restricted data
    - NEVER store raw system secrets
    - NEVER store execution credentials
    """

    # Sensitive keywords to block
    SENSITIVE_KEYWORDS = [
        "password",
        "token",
        "secret",
        "api_key",
        "credential",
        "private_key",
        "auth",
        "session_token",
        "csrf",
        "jwt",
    ]

    # Blocked keys
    BLOCKED_KEYS = [
        "password",
        "token",
        "secret",
        "api_key",
        "private_key",
        "credentials",
        "auth_token",
        "session_id",
    ]

    def sanitize(self, event: MemoryEvent) -> MemoryEvent | None:
        """
        Sanitize memory event before storage.

        Args:
            event: Memory event to sanitize

        Returns:
            Sanitized event or None if event should be blocked
        """
        # Check event type
        if event.event_type not in ["fact", "tool_result", "user_preference", "state_marker"]:
            logger.warning_data(
                "Blocked memory event - invalid type",
                {"event_type": event.event_type},
            )
            return None

        # Check for sensitive data in data dict
        sanitized_data = self._sanitize_data(event.data)

        if sanitized_data is None:
            logger.warning_data(
                "Blocked memory event - sensitive data detected",
                {"event_type": event.event_type},
            )
            return None

        # Return sanitized event
        return MemoryEvent(
            event_type=event.event_type,
            data=sanitized_data,
            timestamp=event.timestamp,
        )

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Sanitize data dictionary.

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data or None if blocked
        """
        if not isinstance(data, dict):
            return None

        sanitized = {}

        for key, value in data.items():
            # Check if key is blocked
            if self._is_blocked_key(key):
                logger.debug_data(
                    "Blocked sensitive key in memory event",
                    {"key": key},
                )
                return None

            # Check if value contains sensitive keywords
            if isinstance(value, str) and self._contains_sensitive_data(value):
                logger.debug_data(
                    "Blocked sensitive value in memory event",
                    {"key": key},
                )
                return None

            sanitized[key] = value

        return sanitized

    def _is_blocked_key(self, key: str) -> bool:
        """Check if key is blocked."""
        return key.lower() in self.BLOCKED_KEYS

    def _contains_sensitive_data(self, value: str) -> bool:
        """Check if value contains sensitive keywords."""
        value_lower = value.lower()
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in value_lower:
                return True
        return False
