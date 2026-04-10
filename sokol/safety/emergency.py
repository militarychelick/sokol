"""Emergency stop handler."""

import threading
from typing import Callable

from sokol.core.constants import EMERGENCY_STOP_HOTKEY
from sokol.observability.logging import get_logger

logger = get_logger("sokol.safety.emergency")


class EmergencyStopHandler:
    """
    Emergency stop handler.

    Coordinates immediate shutdown of all agent activity.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[str], None]] = []
        self._triggered = False
        self._lock = threading.Lock()
        self._hotkey_registered = False

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be called on emergency stop."""
        with self._lock:
            self._callbacks.append(callback)

        logger.debug_data(
            "Emergency stop callback registered",
            {"callback": str(callback)},
        )

    def unregister_callback(self, callback: Callable[[str], None]) -> bool:
        """Unregister a callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
                return True
            return False

    def trigger(self, reason: str = "user_triggered") -> None:
        """
        Trigger emergency stop.

        Calls all registered callbacks immediately.
        """
        with self._lock:
            if self._triggered:
                logger.warning("Emergency stop already triggered")
                return

            self._triggered = True
            callbacks = list(self._callbacks)

        logger.warning_data(
            "EMERGENCY STOP TRIGGERED",
            {"reason": reason, "callbacks_count": len(callbacks)},
        )

        # Call all callbacks
        for callback in callbacks:
            try:
                callback(reason)
            except Exception as e:
                logger.error_data(
                    "Emergency stop callback error",
                    {"callback": str(callback), "error": str(e)},
                )

    def reset(self) -> None:
        """Reset emergency stop state."""
        with self._lock:
            self._triggered = False

        logger.info("Emergency stop reset")

    def is_triggered(self) -> bool:
        """Check if emergency stop has been triggered."""
        return self._triggered

    def register_hotkey(
        self,
        hotkey: str | None = None,
        callback: Callable[[str], None] | None = None,
    ) -> bool:
        """
        Register global hotkey for emergency stop.

        Note: This requires keyboard library or similar.
        For now, returns False to indicate not implemented.
        """
        hotkey = hotkey or EMERGENCY_STOP_HOTKEY

        # TODO: Implement with pynput or keyboard library
        # For now, just log the intent
        logger.info_data(
            "Emergency stop hotkey registration requested",
            {"hotkey": hotkey, "status": "not_implemented"},
        )

        self._hotkey_registered = False
        return False

    def unregister_hotkey(self) -> None:
        """Unregister emergency stop hotkey."""
        if self._hotkey_registered:
            logger.info("Emergency stop hotkey unregistered")
            self._hotkey_registered = False


# Global emergency stop handler
_emergency_handler: EmergencyStopHandler | None = None


def get_emergency_handler() -> EmergencyStopHandler:
    """Get global emergency stop handler."""
    global _emergency_handler
    if _emergency_handler is None:
        _emergency_handler = EmergencyStopHandler()
    return _emergency_handler


def trigger_emergency_stop(reason: str = "user_triggered") -> None:
    """Trigger global emergency stop."""
    get_emergency_handler().trigger(reason)


def register_emergency_callback(callback: Callable[[str], None]) -> None:
    """Register callback for emergency stop."""
    get_emergency_handler().register_callback(callback)


def register_emergency_hotkey(hotkey: str | None = None) -> bool:
    """Register global hotkey for emergency stop."""
    return get_emergency_handler().register_hotkey(hotkey)
