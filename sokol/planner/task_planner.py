"""
Task planner - Optional planning for complex/ambiguous tasks
"""

from __future__ import annotations

from typing import Any

from ..core.intent import Intent


class TaskPlanner:
    """Optional task planner for complex/ambiguous tasks."""
    
    def __init__(self, config: Any) -> None:
        self.config = config
    
    def needs_planning(self, intent: Intent) -> bool:
        """Check if intent requires planning."""
        # For v2, minimal planning - only if complexity > 5
        return intent.complexity > 5
    
    async def create_plan(self, intent: Intent) -> Any:
        """Create execution plan for intent."""
        # For v2, minimal planning - just return intent
        return intent
