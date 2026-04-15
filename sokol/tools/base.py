"""Tool base class and schema definition."""

import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from sokol.core.types import RiskLevel, ToolSchema as CoreToolSchema
from sokol.core.types import ToolResult as CoreToolResult
from sokol.runtime.result import Result
from sokol.runtime.errors import ErrorBuilder, ErrorCategory
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
    def get_schema(self) -> Result[dict] | dict[str, Any]:
        """Get JSON Schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **params: Any) -> Result[ToolResult[T]]:
        """Execute the tool with given parameters."""
        pass

    def undo(self, undo_info: dict[str, Any] | None = None) -> Result[ToolResult[bool]]:
        """
        Undo the last action.

        Returns success=True if undo was successful.
        """
        if not self.undo_support:
            return Result.ok(
                ToolResult(
                    success=False,
                    error="Tool does not support undo",
                    undo_available=False,
                )
            )

        undo_info = undo_info or self._undo_info
        if not undo_info:
            return Result.ok(
                ToolResult(
                    success=False,
                    error="No undo information available",
                    undo_available=False,
                )
            )

        # Subclasses should override this
        return Result.ok(
            ToolResult(
                success=False,
                error="Undo not implemented",
                undo_available=False,
            )
        )

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate parameters against schema.

        Returns (is_valid, error_message).
        """
        schema_result = self.get_schema()
        if isinstance(schema_result, Result):
            if not schema_result.success:
                return False, f"Schema unavailable: {schema_result.error.user_message if schema_result.error else 'unknown'}"
            schema = schema_result.value or {}
        else:
            schema = schema_result
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
        schema_result = self.get_schema()
        parameters: dict[str, Any]
        if isinstance(schema_result, Result):
            parameters = schema_result.value if schema_result.success and schema_result.value is not None else {}
        else:
            parameters = schema_result
        return CoreToolSchema(
            name=self.name,
            description=self.description,
            parameters=parameters,
            risk_level=self.risk_level,
            undo_support=self.undo_support,
            examples=self.examples,
        )

    def safe_execute(self, **params: Any) -> Result[ToolResult[T]]:
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
            return Result.ok(
                ToolResult(
                    success=False,
                    error="Emergency stop triggered before execution",
                    risk_level=self.risk_level,
                    execution_time=time.time() - start_time,
                )
            )

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            logger.warning_data(
                "Tool execution failed - validation error",
                {"tool": tool_name, "error": error},
            )
            return Result.ok(
                ToolResult(
                    success=False,
                    error=error,
                    risk_level=self.risk_level,
                    execution_time=time.time() - start_time,
                )
            )

        # Execute with timeout guard.
        # For side-effecting tools, avoid detached background execution on timeout.
        if self.risk_level in (RiskLevel.WRITE, RiskLevel.DANGEROUS):
            try:
                result = self.execute(**params)
            except Exception as e:
                duration = time.time() - start_time
                logger.error_data(
                    "Tool execution failed - exception",
                    {"tool": tool_name, "error": str(e), "duration": duration},
                )
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=str(e),
                        execution_time=duration,
                        risk_level=self.risk_level,
                    )
                )

            if result is not None and result.success:
                tool_result = result.value
                duration = time.time() - start_time
                tool_result.execution_time = duration
                if tool_result.risk_level is None:
                    tool_result.risk_level = self.risk_level
                self._last_result = tool_result
                return result

            raise RuntimeError(
                f"Tool execution contract violation: {tool_name} returned invalid Result in synchronous mode."
            )

        # Execute with timeout guard
        result: Result[ToolResult[T]] | None = None
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
            return Result.ok(
                ToolResult(
                    success=False,
                    error=f"Tool execution timeout after {self._timeout} seconds",
                    risk_level=self.risk_level,
                    execution_time=self._timeout,
                )
            )

        # Check for exception
        if exception is not None:
            duration = time.time() - start_time
            logger.error_data(
                "Tool execution failed - exception",
                {"tool": tool_name, "error": str(exception), "duration": duration},
            )
            return Result.ok(
                ToolResult(
                    success=False,
                    error=str(exception),
                    execution_time=duration,
                    risk_level=self.risk_level,
                )
            )

        # Success
        if result is not None and result.success:
            tool_result = result.value
            duration = time.time() - start_time
            tool_result.execution_time = duration
            if tool_result.risk_level is None:
                tool_result.risk_level = self.risk_level
            self._last_result = tool_result

            logger.info_data(
                "Tool execution completed",
                {
                    "tool": tool_name,
                    "success": tool_result.success,
                    "duration": duration,
                },
            )

            return result

        # PHASE B B4 FIX: Remove fallback logic (no silent recovery)
        # Tool must NEVER "recover silently" - explicit error handling required
        # If we reach here, it's a contract violation - raise error
        raise RuntimeError(
            f"Tool execution contract violation: {tool_name} returned None result without explicit error handling. "
            f"PHASE B requires explicit Result[T] return or explicit error handling."
        )

    def __repr__(self) -> str:
        return f"Tool(name={self.name}, risk={self.risk_level.value})"
