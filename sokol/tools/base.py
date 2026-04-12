"""Tool base class and schema definition."""

import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from sokol.core.types import RiskLevel, ToolSchema as CoreToolSchema
from sokol.core.types import ToolResult as CoreToolResult
from sokol.observability.logging import get_logger

logger = get_logger("sokol.tools.base")

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
        self._emergency_stop_callback: Any = None
        self._timeout: float = 30.0  # Default timeout in seconds

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

    @property
    def timeout(self) -> float:
        """Tool execution timeout in seconds."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        """Set tool execution timeout in seconds."""
        self._timeout = value

    def set_emergency_stop_callback(self, callback: Any) -> None:
        """Set callback to check for emergency stop during execution."""
        self._emergency_stop_callback = callback

    def _check_emergency_stop(self) -> bool:
        """Check if emergency stop has been triggered."""
        if self._emergency_stop_callback:
            try:
                return self._emergency_stop_callback()
            except Exception:
                return False
        return False

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
        Execute with validation, timing, and timeout guard.

        This is the preferred entry point for tool execution.
        """
        start_time = time.time()
        tool_name = self.name

        logger.info_data(
            "Tool execution started",
            {
                "tool": tool_name,
                "params": str(params)[:200],
                "timeout": self._timeout,
            },
        )

        # Check for emergency stop before execution
        if self._check_emergency_stop():
            logger.warning_data(
                "Tool execution aborted - emergency stop",
                {"tool": tool_name},
            )
            return ToolResult(
                success=False,
                error="Emergency stop triggered before execution",
                risk_level=self.risk_level,
                execution_time=time.time() - start_time,
            )

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            logger.warning_data(
                "Tool execution failed - validation error",
                {"tool": tool_name, "error": error},
            )
            return ToolResult(
                success=False,
                error=error,
                risk_level=self.risk_level,
                execution_time=time.time() - start_time,
            )

        # Execute with timeout guard
        result: ToolResult[T] | None = None
        exception: Exception | None = None
        timeout_occurred = False

        def execute_wrapper() -> None:
            nonlocal result, exception
            try:
                result = self.execute(**params)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=execute_wrapper)
        thread.start()
        thread.join(timeout=self._timeout)

        if thread.is_alive():
            # Timeout occurred
            timeout_occurred = True
            logger.error_data(
                "Tool execution timeout",
                {"tool": tool_name, "timeout": self._timeout},
            )
            return ToolResult(
                success=False,
                error=f"Tool execution timeout after {self._timeout} seconds",
                risk_level=self.risk_level,
                execution_time=self._timeout,
            )

        # Check for exception
        if exception is not None:
            duration = time.time() - start_time
            logger.error_data(
                "Tool execution failed - exception",
                {"tool": tool_name, "error": str(exception), "duration": duration},
            )
            return ToolResult(
                success=False,
                error=str(exception),
                execution_time=duration,
                risk_level=self.risk_level,
            )

        # Success
        if result is not None:
            duration = time.time() - start_time
            result.execution_time = duration
            result.risk_level = self.risk_level
            self._last_result = result

            logger.info_data(
                "Tool execution completed",
                {
                    "tool": tool_name,
                    "success": result.success,
                    "duration": duration,
                },
            )

            return result

        # Fallback (should not reach here)
        logger.error_data(
            "Tool execution failed - no result",
            {"tool": tool_name},
        )
        return ToolResult(
            success=False,
            error="Tool execution failed - no result returned",
            execution_time=time.time() - start_time,
            risk_level=self.risk_level,
        )

    def __repr__(self) -> str:
        return f"Tool(name={self.name}, risk={self.risk_level.value})"
