"""
App launcher tool - Simple wrapper for app launching
"""

from typing import Any


class AppLauncherTool:
    """Tool for launching applications."""
    
    def __init__(self, executor: Any) -> None:
        self.executor = executor
    
    def launch(self, app_name: str, path: str | None = None) -> dict[str, Any]:
        """Launch an application."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="launch",
            action_category=ActionCategory.APP_LAUNCH,
            params={"app": app_name, "path": path},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
        }
    
    def close(self, app_name: str) -> dict[str, Any]:
        """Close an application."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="close",
            action_category=ActionCategory.APP_CLOSE,
            params={"app": app_name},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
