"""
File search tool - Simple wrapper for file operations
"""

from typing import Any


class FileSearchTool:
    """Tool for file operations."""
    
    def __init__(self, executor: Any) -> None:
        self.executor = executor
    
    def search(self, query: str, directory: str | None = None) -> dict[str, Any]:
        """Search for files."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="search",
            action_category=ActionCategory.FILE_SEARCH,
            params={"query": query, "directory": directory},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
            "results": result.data.get("results", []) if result.data else [],
            "total": result.data.get("total", 0) if result.data else 0,
        }
    
    def open(self, path: str) -> dict[str, Any]:
        """Open a file."""
        from ..core.agent import Step
        from ..core.constants import ActionCategory
        
        step = Step(
            action="open",
            action_category=ActionCategory.FILE_OPEN,
            params={"path": path},
        )
        
        result = self.executor.execute_step(step)
        
        return {
            "success": result.success,
            "message": result.message,
        }
