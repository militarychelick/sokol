"""Tool Execution Contract Layer - strict tool interaction standardization."""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
from datetime import datetime
import time

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.tool_contract")


class ErrorType(str, Enum):
    """Standardized error types for tool execution."""

    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class ToolCallContract:
    """Unified contract for tool calls."""

    tool_id: str
    input: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"  # low/medium/high
    task_id: Optional[str] = None
    trace_id: str = ""


@dataclass
class ToolResultContract:
    """Standardized contract for tool results."""

    tool_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0


class ToolContractNormalizer:
    """
    Tool contract normalizer - enforces strict structure on tool interactions.

    This normalizer:
    - Normalizes tool inputs before execution
    - Normalizes tool outputs after execution
    - Validates schemas
    - Injects defaults
    - Ensures type safety
    - Attaches trace IDs
    - Wraps errors into standardized format

    This normalizer DOES NOT:
    - Change execution logic
    - Change router decisions
    - Change control layer logic
    - Change tool selection logic
    - Introduce new execution loops
    - Add async systems
    - Add background processing
    - Add autonomy

    This normalizer ONLY:
    - Enforces structure
    - Sanitizes inputs/outputs
    - Logs violations
    """

    def __init__(self) -> None:
        """Initialize tool contract normalizer."""
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def normalize_input(
        self,
        tool_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any] | None = None,
        risk_level: str = "low",
        task_id: Optional[str] = None,
        trace_id: str = "",
    ) -> ToolCallContract:
        """
        Normalize tool input before execution.

        Args:
            tool_id: Tool ID
            input_data: Raw input data
            context: Execution context
            risk_level: Risk level
            task_id: Optional task ID
            trace_id: Trace ID

        Returns:
            Normalized ToolCallContract
        """
        start_time = time.time()

        # Validate schema
        schema = self._get_tool_schema(tool_id)
        if schema:
            input_data = self._validate_and_coerce_input(input_data, schema, tool_id)

        # PHASE B B1: Validate input schema with contract validator
        from sokol.runtime.contract_validator import validate_tool_input_schema
        validate_tool_input_schema(tool_id, input_data, schema)

        # Attach trace_id if missing
        if not trace_id:
            trace_id = self._generate_trace_id()

        # Create contract
        contract = ToolCallContract(
            tool_id=tool_id,
            input=input_data,
            context=context or {},
            risk_level=risk_level,
            task_id=task_id,
            trace_id=trace_id,
        )

        # Log normalization
        elapsed = (time.time() - start_time) * 1000
        logger.debug_data(
            "Tool input normalized",
            {
                "tool_id": tool_id,
                "trace_id": trace_id,
                "input_keys": list(input_data.keys()),
                "normalization_time_ms": elapsed,
            },
        )

        return contract

    def normalize_output(
        self,
        tool_id: str,
        raw_result: Any,
        execution_time_ms: float = 0.0,
        retry_count: int = 0,
        error: Optional[str] = None,
        error_type: Optional[ErrorType] = None,
    ) -> ToolResultContract:
        """
        Normalize tool output after execution.

        Args:
            tool_id: Tool ID
            raw_result: Raw tool result
            execution_time_ms: Execution time in milliseconds
            retry_count: Retry count
            error: Optional error message
            error_type: Optional error type

        Returns:
            Normalized ToolResultContract
        """
        start_time = time.time()

        # Determine success - default to False (strict validation)
        # Cannot assume success, must be explicitly validated
        success = False

        # If raw_result has success field, use it (explicit validation)
        if hasattr(raw_result, "success"):
            success = raw_result.success
            if hasattr(raw_result, "data"):
                result = raw_result.data
            elif hasattr(raw_result, "error"):
                error = raw_result.error
                success = False
            else:
                result = raw_result
        elif error is None:
            # No error field and no error provided - still cannot assume success
            # Result structure is invalid, mark as failure
            logger.warning_data(
                "Tool result missing success field, treating as failure",
                {"tool_id": tool_id},
            )
            error = "Tool result missing success field - invalid contract"
            result = raw_result
        else:
            # Error provided, result is failure
            result = raw_result

        # Infer error type if not provided
        if error and not error_type:
            error_type = self._infer_error_type(error)

        # PHASE B B1: Validate output schema with contract validator
        from sokol.runtime.contract_validator import validate_tool_output_schema
        schema = self._get_tool_schema(tool_id)
        if success:
            validate_tool_output_schema(tool_id, result, schema)

        # Create contract
        contract = ToolResultContract(
            tool_id=tool_id,
            success=success,
            result=result if success else None,
            error=error if not success else None,
            error_type=error_type if not success else None,
            execution_time_ms=execution_time_ms,
            retry_count=retry_count,
            metadata={
                "normalized_at": datetime.now().isoformat(),
            },
        )

        # Log normalization
        elapsed = (time.time() - start_time) * 1000
        logger.debug_data(
            "Tool output normalized",
            {
                "tool_id": tool_id,
                "success": success,
                "error_type": error_type.value if error_type else None,
                "normalization_time_ms": elapsed,
            },
        )

        return contract

    def _get_tool_schema(self, tool_id: str) -> dict[str, Any] | None:
        """
        Get tool schema from cache or fetch from tool registry.

        Args:
            tool_id: Tool ID

        Returns:
            Tool schema or None
        """
        if tool_id in self._schema_cache:
            return self._schema_cache[tool_id]

        try:
            from sokol.tools.registry import get_registry

            registry = get_registry()
            schema = registry.get_schema(tool_id)
            if schema is None:
                return None

            schema_dict = {
                "type": "object",
                "properties": schema.parameters.get("properties", {}) if isinstance(schema.parameters, dict) else {},
                "required": schema.parameters.get("required", []) if isinstance(schema.parameters, dict) else [],
            }
            self._schema_cache[tool_id] = schema_dict
            return schema_dict
        except Exception as e:
            logger.warning_data(
                "Failed to resolve tool schema from registry",
                {"tool_id": tool_id, "error": str(e)},
            )
            return None

    def _validate_and_coerce_input(
        self,
        input_data: dict[str, Any],
        schema: dict[str, Any],
        tool_id: str,
    ) -> dict[str, Any]:
        """
        Validate and coerce input data against schema.

        Args:
            input_data: Input data
            schema: Tool schema
            tool_id: Tool ID

        Returns:
            Coerced input data
        """
        # This is a placeholder - would perform actual schema validation
        # For now, return input as-is (sanitization only)
        return input_data

    def _infer_error_type(self, error_message: str) -> ErrorType:
        """
        Infer error type from error message.

        Args:
            error_message: Error message

        Returns:
            Inferred error type
        """
        error_lower = error_message.lower()

        if "timeout" in error_lower:
            return ErrorType.TIMEOUT
        elif "validation" in error_lower or "invalid" in error_lower:
            return ErrorType.VALIDATION_ERROR
        elif "blocked" in error_lower or "denied" in error_lower:
            return ErrorType.BLOCKED
        elif "execution" in error_lower:
            return ErrorType.EXECUTION_ERROR
        else:
            return ErrorType.UNKNOWN

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID."""
        import uuid
        return f"trace_{uuid.uuid4().hex[:8]}"
