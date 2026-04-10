"""Tool registry for discovery and execution."""

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Type

from sokol.core.types import RiskLevel, ToolSchema
from sokol.observability.logging import get_logger
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.registry")


class ToolRegistry:
    """
    Registry for all available tools.

    Provides:
    - Tool discovery and registration
    - Tool lookup by name
    - Tool execution with safety checks
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any]] = {}
        self._schemas: dict[str, ToolSchema] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: Tool[Any]) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            logger.warning_data(
                "Tool already registered, replacing",
                {"tool": tool.name},
            )

        self._tools[tool.name] = tool
        self._schemas[tool.name] = tool.get_tool_schema()

        logger.info_data(
            "Tool registered",
            {
                "tool": tool.name,
                "risk": tool.risk_level.value,
                "undo_support": tool.undo_support,
            },
        )

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            del self._schemas[tool_name]
            logger.info_data("Tool unregistered", {"tool": tool_name})
            return True
        return False

    def get(self, tool_name: str) -> Tool[Any] | None:
        """Get tool by name."""
        return self._tools.get(tool_name)

    def get_schema(self, tool_name: str) -> ToolSchema | None:
        """Get tool schema by name."""
        return self._schemas.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """Check if tool exists."""
        return tool_name in self._tools

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_schemas(self) -> list[ToolSchema]:
        """List all tool schemas."""
        return list(self._schemas.values())

    def list_by_risk(self, risk_level: RiskLevel) -> list[str]:
        """List tools by risk level."""
        return [
            name
            for name, schema in self._schemas.items()
            if schema.risk_level == risk_level
        ]

    def get_dangerous_tools(self) -> list[str]:
        """Get list of dangerous tools."""
        return self.list_by_risk(RiskLevel.DANGEROUS)

    def get_write_tools(self) -> list[str]:
        """Get list of write tools."""
        return self.list_by_risk(RiskLevel.WRITE)

    def get_read_tools(self) -> list[str]:
        """Get list of read-only tools."""
        return self.list_by_risk(RiskLevel.READ)

    def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> ToolResult[Any]:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        logger.info_data(
            "Executing tool",
            {"tool": tool_name, "params": str(params)[:100]},
        )

        return tool.safe_execute(**params)

    def discover_tools(self, package_path: str = "sokol.tools.builtin") -> int:
        """
        Auto-discover and register tools from a package.

        Returns number of tools registered.
        """
        count = 0

        try:
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent

            for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
                if module_name.startswith("_"):
                    continue

                try:
                    module = importlib.import_module(f"{package_path}.{module_name}")

                    # Look for Tool subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, Tool)
                            and attr is not Tool
                        ):
                            try:
                                tool_instance = attr()
                                self.register(tool_instance)
                                count += 1
                            except Exception as e:
                                logger.error_data(
                                    "Failed to instantiate tool",
                                    {"module": module_name, "class": attr_name, "error": str(e)},
                                )

                except Exception as e:
                    logger.error_data(
                        "Failed to load tool module",
                        {"module": module_name, "error": str(e)},
                    )

        except Exception as e:
            logger.error_data(
                "Failed to discover tools",
                {"package": package_path, "error": str(e)},
            )

        logger.info_data("Tool discovery complete", {"tools_registered": count})
        return count

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._schemas.clear()
        self._categories.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self._tools)})"


# Global registry instance
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _registry.discover_tools()
    return _registry
