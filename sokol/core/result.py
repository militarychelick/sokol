"""
ActionResult - Unified result format for Sokol v2
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActionResult:
    """Unified action result format."""
    success: bool
    action: str
    message: str
    data: dict | None = None
    error: str | None = None
