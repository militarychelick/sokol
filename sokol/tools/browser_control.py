"""
Browser control tool - Simple wrapper for browser operations
"""

from typing import Any


class BrowserTool:
    """Tool for browser control."""
    
    def __init__(self, executor: Any) -> None:
        self.executor = executor
    
    def open_url(self, url: str, browser: str | None = None) -> dict[str, Any]:
        """Open a URL in browser."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="open_url",
            action_category=ActionCategory.BROWSER_NAVIGATE,
            params={"url": url, "browser": browser},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
    
    def open_browser(self, browser: str = "chrome") -> dict[str, Any]:
        """Open a browser."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="open_browser",
            action_category=ActionCategory.BROWSER_OPEN,
            params={"browser": browser},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
