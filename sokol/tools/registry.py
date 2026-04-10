"""
Tool registry - Register and discover tools
"""

from __future__ import annotations

from typing import Any, Callable


class ToolRegistry:
    """
    Registry for available tools.
    
    Simple registry without complex plugin system.
    Tools are registered manually.
    """
    
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}
    
    def register(self, name: str, tool: Any) -> None:
        """Register a tool."""
        self._tools[name] = tool
    
    def get(self, name: str) -> Any | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def execute(self, name: str, **kwargs: Any) -> Any:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")
        
        if callable(tool):
            return tool(**kwargs)
        
        # Assume tool has execute method
        if hasattr(tool, "execute"):
            return tool.execute(**kwargs)
        
        raise ValueError(f"Tool has no execute method: {name}")
