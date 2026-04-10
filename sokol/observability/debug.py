"""Debug mode utilities."""

import os
from contextlib import contextmanager
from typing import Generator

# Debug mode flag
_debug_mode: bool = False


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    global _debug_mode
    # Also check environment variable
    return _debug_mode or os.environ.get("SOKOL_DEBUG", "").lower() in ("1", "true", "yes")


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode."""
    global _debug_mode
    _debug_mode = enabled


class DebugMode:
    """Context manager for debug mode."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._previous: bool | None = None

    def __enter__(self) -> "DebugMode":
        global _debug_mode
        self._previous = _debug_mode
        _debug_mode = self._enabled
        return self

    def __exit__(self, *args: object) -> None:
        global _debug_mode
        if self._previous is not None:
            _debug_mode = self._previous


@contextmanager
def debug_context(enabled: bool = True) -> Generator[None, None, None]:
    """Context manager for temporary debug mode."""
    with DebugMode(enabled):
        yield


def dry_run_mode() -> bool:
    """Check if dry-run mode is enabled (no real actions)."""
    return os.environ.get("SOKOL_DRY_RUN", "").lower() in ("1", "true", "yes")


class DryRun:
    """Context manager for dry-run mode."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._previous: str | None = None

    def __enter__(self) -> "DryRun":
        self._previous = os.environ.get("SOKOL_DRY_RUN")
        os.environ["SOKOL_DRY_RUN"] = "1" if self._enabled else "0"
        return self

    def __exit__(self, *args: object) -> None:
        if self._previous is None:
            os.environ.pop("SOKOL_DRY_RUN", None)
        else:
            os.environ["SOKOL_DRY_RUN"] = self._previous
