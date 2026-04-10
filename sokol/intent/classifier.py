"""
Intent classifier - Determine complexity and execution path
"""

from __future__ import annotations

from ..core.agent import Intent
from ..core.constants import IntentType


class IntentClassifier:
    """
    Classifies intents by complexity and execution requirements.
    
    Simple intents -> Direct execution
    Complex intents -> Planning required
    """
    
    # Keywords that indicate complex tasks
    COMPLEX_KEYWORDS = {
        "and", "then", "after", "also", "while",
        "setup", "prepare", "organize", "multiple",
        "workflow", "sequence", "chain",
    }
    
    # Keywords that indicate workflows
    WORKFLOW_KEYWORDS = {
        "workspace", "routine", "setup", "environment",
        "meeting", "presentation", "project",
    }
    
    def classify(self, intent: Intent) -> Intent:
        """
        Classify intent and update complexity.
        
        Args:
            intent: Parsed intent
        
        Returns:
            Updated intent with refined classification
        """
        text = intent.raw_text.lower()
        
        # Check for workflow indicators
        if any(kw in text for kw in self.WORKFLOW_KEYWORDS):
            intent.intent_type = IntentType.WORKFLOW
            intent.complexity = max(intent.complexity, 7)
        
        # Check for multiple actions
        if any(kw in text for kw in self.COMPLEX_KEYWORDS):
            intent.complexity = max(intent.complexity, 5)
        
        # Count action verbs
        action_count = self._count_actions(text)
        if action_count > 1:
            intent.complexity = max(intent.complexity, 4 + action_count)
        
        return intent
    
    def _count_actions(self, text: str) -> int:
        """Count action verbs in text."""
        action_verbs = {
            "open", "close", "launch", "start", "run",
            "find", "search", "play", "pause", "stop",
            "minimize", "maximize", "switch", "create",
            "delete", "copy", "move", "download", "upload",
        }
        
        count = 0
        for verb in action_verbs:
            if verb in text:
                count += 1
        
        return count
    
    def needs_planning(self, intent: Intent) -> bool:
        """Check if intent needs planning."""
        return (
            intent.intent_type == IntentType.WORKFLOW
            or intent.complexity >= 5
            or intent.needs_planning()
        )
    
    def is_conversational(self, intent: Intent) -> bool:
        """Check if intent is just conversation."""
        return intent.intent_type == IntentType.CONVERSATION
