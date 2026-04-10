"""Tool base class and schema definition."""

import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from sokol.core.types import RiskLevel, ToolSchema as CoreToolSchema
from sokol.core.types import ToolResult as CoreToolResult

T = TypeVar("T")


class ToolResult(CoreToolResult[T]):
    """Result from tool execution."""

    pass


class Tool(ABC, Generic[T]):
    """
    Base class for all tools.

    Every tool must implement:
    - name: Unique identifier
    - description: Human-readable description
    - risk_level: READ, WRITE, or DANGEROUS
    - execute: The actual tool logic
    - get_schema: JSON Schema for parameters
    """

    def __init__(self) -> None:
        self._last_result: ToolResult[T] | None = None
        self._undo_info: dict[str, Any] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Risk level of this tool."""
        pass

    @property
    def undo_support(self) -> bool:
        """Whether this tool supports undo."""
        return False

    @property
    def examples(self) -> list[str]:
        """Example usages."""
        return []

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """Get JSON Schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **params: Any) -> ToolResult[T]:
        """Execute the tool with given parameters."""
        pass

    def undo(self, undo_info: dict[str, Any] | None = None) -> ToolResult[bool]:
        """
        Undo the last action.

        Returns success=True if undo was successful.
        """
        if not self.undo_support:
            return ToolResult(
                success=False,
                error="Tool does not support undo",
                undo_available=False,
            )

        undo_info = undo_info or self._undo_info
        if not undo_info:
            return ToolResult(
                success=False,
                error="No undo information available",
                undo_available=False,
            )

        # Subclasses should override this
        return ToolResult(
            success=False,
            error="Undo not implemented",
            undo_available=False,
        )

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate parameters against schema.

        Returns (is_valid, error_message).
        """
        schema = self.get_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required parameters
        for param in required:
            if param not in params:
                return False, f"Missing required parameter: {param}"

        # Check parameter types (basic validation)
        for param, value in params.items():
            if param in properties:
                expected_type = properties[param].get("type")
                if expected_type:
                    if not self._check_type(value, expected_type):
                        return False, f"Parameter {param} has wrong type, expected {expected_type}"

        return True, None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON Schema type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow
        return isinstance(value, expected)

    def get_tool_schema(self) -> CoreToolSchema:
        """Get full tool schema for registry."""
        return CoreToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.get_schema(),
            risk_level=self.risk_level,
            undo_support=self.undo_support,
            examples=self.examples,
        )

    def safe_execute(self, **params: Any) -> ToolResult[T]:
        """
        Execute with validation and timing.

        This is the preferred entry point for tool execution.
        """
        start_time = time.time()

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            return ToolResult(
                success=False,
                error=error,
                risk_level=self.risk_level,
            )

        try:
            result = self.execute(**params)
            result.execution_time = time.time() - start_time
            result.risk_level = self.risk_level
            self._last_result = result
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                risk_level=self.risk_level,
            )

    def __repr__(self) -> str:
        return f"Tool(name={self.name}, risk={self.risk_level.value})"
