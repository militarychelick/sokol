"""
Safety policy for Sokol v2
"""

from __future__ import annotations

from typing import Any

from ..core.intent import Intent, SafetyLevel


class SafetyPolicy:
    """Safety policy for action classification."""
    
    def __init__(self, config: Any) -> None:
        self.config = config
    
    def classify(self, intent: Intent) -> SafetyLevel:
        """Classify safety level for intent."""
        # Use intent's safety level if already set
        if intent.safety_level != SafetyLevel.SAFE:
            return intent.safety_level
        
        # Classify based on action_type
        dangerous_actions = ["close_app", "system_action"]
        caution_actions = ["manage_window", "open_file"]
        
        if intent.action_type in dangerous_actions:
            return SafetyLevel.DANGEROUS
        elif intent.action_type in caution_actions:
            return SafetyLevel.CAUTION
        
        return SafetyLevel.SAFE
