"""
Task planner - Minimal implementation for v2
"""

from __future__ import annotations

from typing import Any

from ..core.agent import Intent, Plan, Step
from ..core.config import Config


class TaskPlanner:
    """
    Minimal task planner for v2.
    
    For now, simple tasks don't need planning.
    Complex tasks will be implemented later.
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    async def create_plan(self, intent: Intent) -> Plan:
        """Create execution plan for intent."""
        # For v2, we don't do complex planning
        # Simple tasks are executed directly
        # If complexity > 3, we'll just return a single step
        step = Step(
            action="direct_execute",
            action_category=intent.action_category or intent.action_category,
            params=intent.entities,
        )
        
        return Plan(
            intent=intent,
            steps=[step],
            status="pending",
        )
    
    async def handle_failure(self, plan: Plan, step: Step, error: Any) -> str:
        """Handle execution failure."""
        return "abort"  # For now, abort on failure
