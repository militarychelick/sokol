"""
Window manager tool - Simple wrapper for window control
"""

from typing import Any


class WindowManagerTool:
    """Tool for managing windows."""
    
    def __init__(self, executor: Any) -> None:
        self.executor = executor
    
    def activate(self, title: str) -> dict[str, Any]:
        """Activate a window."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="window_activate",
            action_category=ActionCategory.WINDOW_MANAGE,
            params={"title": title},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
    
    def minimize(self, title: str) -> dict[str, Any]:
        """Minimize a window."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="window_minimize",
            action_category=ActionCategory.WINDOW_MANAGE,
            params={"title": title},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
    
    def maximize(self, title: str) -> dict[str, Any]:
        """Maximize a window."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="window_maximize",
            action_category=ActionCategory.WINDOW_MANAGE,
            params={"title": title},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
