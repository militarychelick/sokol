"""
Safety checker - Evaluate action safety
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config


class SafetyChecker:
    """Safety checker for actions."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def check_action(self, action: str, params: dict[str, Any]) -> str:
        """Check action safety level."""
        dangerous_actions = ["system_action", "code_execution"]
        caution_actions = ["close_app", "delete_file", "modify_file"]
        
        if action in dangerous_actions:
            return "dangerous"
        elif action in caution_actions:
            return "caution"
        else:
            return "safe"
    
    def requires_confirmation(self, safety_level: str) -> bool:
        """Check if action requires confirmation."""
        if safety_level == "dangerous":
            return True
        if safety_level == "caution":
            return True
        return False
