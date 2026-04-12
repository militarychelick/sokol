"""Emergency stop handler."""

import threading
from typing import Callable

from sokol.core.constants import EMERGENCY_STOP_HOTKEY
from sokol.observability.logging import get_logger

logger = get_logger("sokol.safety.emergency")

# Try to import pynput for hotkey support
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput not available, emergency hotkey will not work")


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
        self._hotkey_listener: keyboard.Listener | None = None
        self._hotkey_thread: threading.Thread | None = None

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

        Uses pynput library for cross-platform hotkey support.
        """
        if not PYNPUT_AVAILABLE:
            logger.warning("pynput not available, cannot register hotkey")
            return False

        hotkey = hotkey or EMERGENCY_STOP_HOTKEY

        # Parse hotkey string (e.g., "ctrl+alt+shift+escape")
        try:
            # Convert string to pynput hotkey format
            hotkey_parts = hotkey.lower().split('+')
            key_combination = []
            for part in hotkey_parts:
                part = part.strip()
                if part == 'ctrl':
                    key_combination.append(keyboard.Key.ctrl)
                elif part == 'alt':
                    key_combination.append(keyboard.Key.alt)
                elif part == 'shift':
                    key_combination.append(keyboard.Key.shift)
                elif part == 'escape':
                    key_combination.append(keyboard.Key.esc)
                elif part == 'cmd' or part == 'win':
                    key_combination.append(keyboard.Key.cmd)
                else:
                    # Try as regular character key
                    if len(part) == 1:
                        key_combination.append(keyboard.KeyCode.from_char(part))
                    else:
                        logger.warning_data(
                            "Unknown hotkey component",
                            {"component": part},
                        )
                        return False

            # Create hotkey function
            def on_activate():
                logger.info("Emergency stop hotkey activated")
                self.trigger("hotkey")
                if callback:
                    callback("hotkey")

            # Register the hotkey
            self._hotkey_listener = keyboard.GlobalHotKeys({
                tuple(key_combination): on_activate
            })

            # Start listener in a separate thread
            self._hotkey_thread = threading.Thread(
                target=self._hotkey_listener.start,
                daemon=True,
                name="EmergencyHotkey"
            )
            self._hotkey_thread.start()

            self._hotkey_registered = True
            logger.info_data(
                "Emergency stop hotkey registered",
                {"hotkey": hotkey},
            )
            return True

        except Exception as e:
            logger.error_data(
                "Failed to register emergency hotkey",
                {"error": str(e), "hotkey": hotkey},
            )
            self._hotkey_registered = False
            return False

    def unregister_hotkey(self) -> None:
        """Unregister emergency stop hotkey."""
        if self._hotkey_registered:
            if self._hotkey_listener:
                self._hotkey_listener.stop()
                if self._hotkey_thread and self._hotkey_thread.is_alive():
                    self._hotkey_thread.join(timeout=2.0)
            self._hotkey_listener = None
            self._hotkey_thread = None
            self._hotkey_registered = False
            logger.info("Emergency stop hotkey unregistered")


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
