"""
Task planner - Optional planning for complex/ambiguous tasks
"""

from __future__ import annotations

from typing import Any

from ..core.agent import Intent, Plan, Step
from ..core.config import Config


class TaskPlanner:
    """
    Optional task planner for complex/ambiguous tasks.
    
    Only triggered when:
    - complexity > 5
    - ambiguity detected (multiple interpretations)
    - multi-step tasks (contains "and", "then")
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def needs_planning(self, intent: Intent) -> bool:
        """Check if intent requires planning."""
        # Complexity threshold
        if intent.complexity > 5:
            return True
        
        # Ambiguity indicators
        ambiguity_indicators = ["and", "then", "after", "before", "и", "потом"]
        text_lower = intent.raw_text.lower()
        
        for indicator in ambiguity_indicators:
            if indicator in text_lower:
                return True
        
        return False
    
    async def create_plan(self, intent: Intent) -> Plan:
        """Create execution plan for intent."""
        # For v2, minimal planning - just return single step
        # Complex planning will be implemented later
        step = Step(
            action=intent.action_type,
            action_category=None,  # Not used in new structure
            params=intent.params,
        )
        
        return Plan(
            intent=intent,
            steps=[step],
            status="pending",
        )
    
    async def handle_failure(self, plan: Plan, step: Step, error: Any) -> str:
        """Handle execution failure."""
        return "abort"  # For now, abort on failure
