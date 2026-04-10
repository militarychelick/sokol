"""
Intent - Strict structured intent for Sokol v2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SafetyLevel(Enum):
    """Safety level for actions."""
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


@dataclass
class Intent:
    """Parsed user intent with strict structure."""
    action_type: str           # "launch_app", "open_url", "press_hotkey", etc.
    target: str | None         # "chrome", "youtube.com", "ctrl+c", etc.
    params: dict = field(default_factory=dict)  # additional parameters
    safety_level: SafetyLevel = SafetyLevel.SAFE
    complexity: int = 1        # 1-10 scale
    requires_planning: bool = False
    raw_text: str = ""         # original input
    
    def is_simple(self) -> bool:
        """Check if intent is simple enough for direct execution."""
        return not self.requires_planning and self.complexity <= 3
