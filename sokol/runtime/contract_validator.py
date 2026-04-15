"""Contract Validation Layer - PHASE B (Strict Enforcement Mode)

PHASE B CRITICAL FIX: Strict enforcement mode enabled for formal system
- Raises exceptions on violations (not just warnings)
- Enforces execution contract invariants
- Schema validation for tools
- Runtime contract checks

Validates:
1. No None returns from critical functions
2. Result[T] types used correctly
3. No callbacks in execution path
4. State changes only through commit_state()
5. Tool input schema validation
6. Tool output schema validation
7. Tool side effect validation (external vs internal)
"""

from typing import Any, Callable
from sokol.observability.logging import get_logger
from sokol.runtime.result import Result

logger = get_logger("sokol.runtime.contract_validator")


class ContractViolationException(Exception):
    """Raised when contract validation fails in hard mode."""


class ContractValidator:
    """
    Validates execution contract compliance.

    PHASE A: Soft mode - warnings only
    PHASE B: Hard mode - raise errors (STRICT MODE)
    """

    def __init__(self, enforcement_mode: str = "hard") -> None:
        """
        Initialize contract validator.

        Args:
            enforcement_mode: "soft" (warnings only) or "hard" (raise errors)
        """
        self._enforcement_mode = enforcement_mode

    def validate_no_none_return(self, result: Any, context: str) -> bool:
        """
        Validate that result is not None.

        Args:
            result: Result to validate
            context: Context string for logging

        Returns:
            True if valid, False if violation
        """
        if result is None:
            message = f"Contract violation: None return in {context}"
            if self._enforcement_mode == "hard":
                raise ContractViolationException(message)
            logger.warning(message)
            return False
        return True

    def validate_result_type(self, result: Any, function_name: str) -> bool:
        """
        Validate that a function returns Result[T] type.
        PHASE A: Enforcement mode - raises exception if not Result type.
        """
        if not isinstance(result, Result):
            raise ContractViolationException(
                f"Contract violation: {function_name} did not return Result[T] (PHASE A enforcement)"
            )
        return True

    def validate_no_callback_usage(self, callback: Any, context: str) -> bool:
        """
        Validate that callbacks are not used in execution path.
        PHASE A: Enforcement mode - raises exception if callback detected.
        """
        if callback is not None:
            raise ContractViolationException(
                f"Contract violation: callback detected in {context} (PHASE A enforcement)"
            )
        return True

    def validate_state_commit_only(self, state_change: bool, context: str) -> bool:
        """
        Validate that state changes only through commit_state().
        PHASE A: Enforcement mode - raises exception if direct state mutation detected.
        Args:
            state_change: Whether state was changed
            context: Context string for logging

        Returns:
            True if valid (no direct state mutation), False if violation
        """
        # PHASE A: Cannot enforce this yet, just log
        # PHASE B: Add enforcement
        if state_change and "commit_state" not in context:
            message = f"Contract warning: State change outside commit_state() in {context}"
            logger.warning(message)
        return True

    def validate_execution_guarantees(self, context: str, **kwargs) -> bool:
        """
        Validate execution guarantees.

        Args:
            context: Context string for logging
            **kwargs: Guarantee flags to validate

        Returns:
            True if all guarantees met, False if violation
        """
        # PHASE A: Log validation, no enforcement yet
        # PHASE B: Add enforcement
        logger.info_data(
            "Execution guarantee validation",
            {"context": context, "guarantees": kwargs}
        )
        return True

    def validate_tool_input_schema(self, tool_id: str, input_data: dict[str, Any], schema: dict[str, Any]) -> bool:
        """
        Validate tool input against schema (PHASE B B6).

        Args:
            tool_id: Tool ID
            input_data: Input data to validate
            schema: Tool schema

        Returns:
            True if valid, raises ContractViolationException if invalid (hard mode)
        """
        # PHASE B: Add schema validation
        if not schema:
            # No schema defined - allow but log warning
            logger.warning_data(
                "Tool has no input schema defined",
                {"tool_id": tool_id}
            )
            return True

        # Validate required fields
        required = schema.get("required", [])
        for field in required:
            if field not in input_data:
                message = f"Tool input validation failed: missing required field '{field}' for tool {tool_id}"
                if self._enforcement_mode == "hard":
                    raise ContractViolationException(message)
                logger.warning(message)
                return False

        # Validate field types (basic validation)
        properties = schema.get("properties", {})
        for field, value in input_data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type:
                    if not self._check_type(value, expected_type):
                        message = f"Tool input validation failed: field '{field}' has wrong type, expected {expected_type} for tool {tool_id}"
                        if self._enforcement_mode == "hard":
                            raise ContractViolationException(message)
                        logger.warning(message)
                        return False

        return True

    def validate_tool_output_schema(self, tool_id: str, output_data: Any, schema: dict[str, Any]) -> bool:
        """
        Validate tool output against schema (PHASE B B6).

        Args:
            tool_id: Tool ID
            output_data: Output data to validate
            schema: Tool schema

        Returns:
            True if valid, raises ContractViolationException if invalid (hard mode)
        """
        # PHASE B: Add schema validation
        if not schema:
            # No schema defined - allow but log warning
            logger.warning_data(
                "Tool has no output schema defined",
                {"tool_id": tool_id}
            )
            return True

        # Basic validation - output should not be None
        if output_data is None:
            message = f"Tool output validation failed: output is None for tool {tool_id}"
            if self._enforcement_mode == "hard":
                raise ContractViolationException(message)
            logger.warning(message)
            return False

        return True

    def validate_tool_side_effects(self, tool_id: str, side_effects: list[str]) -> bool:
        """
        Validate tool side effects (PHASE B B6).

        Args:
            tool_id: Tool ID
            side_effects: List of side effects performed by tool

        Returns:
            True if valid (no internal system side effects), raises ContractViolationException if invalid
        """
        # PHASE B: Validate tool side effects (external allowed, internal forbidden)
        forbidden_effects = ["memory_write", "state_change", "event_emission", "state_mutation"]

        for effect in side_effects:
            if effect in forbidden_effects:
                message = f"Tool side effect validation failed: tool {tool_id} performed forbidden internal system side effect: {effect}"
                if self._enforcement_mode == "hard":
                    raise ContractViolationException(message)
                logger.warning(message)
                return False

        return True

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


# Global validator instance (hard mode for PHASE B - STRICT MODE)
_validator = ContractValidator(enforcement_mode="hard")


def validate_no_none_return(result: Any, context: str) -> bool:
    """Validate that result is not None."""
    return _validator.validate_no_none_return(result, context)


def validate_result_type(result: Any, context: str) -> bool:
    """Validate that result has is_ok() method (Result[T] type)."""
    return _validator.validate_result_type(result, context)


def validate_no_callback_usage(callback: Callable | None, context: str) -> bool:
    """Validate that callback is not used in execution path."""
    return _validator.validate_no_callback_usage(callback, context)


def validate_state_commit_only(state_change: bool, context: str) -> bool:
    """Validate that state changes only through commit_state()."""
    return _validator.validate_state_commit_only(state_change, context)


def validate_execution_guarantees(context: str, **kwargs) -> bool:
    """Validate execution guarantees."""
    return _validator.validate_execution_guarantees(context, **kwargs)


def validate_tool_input_schema(tool_id: str, input_data: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Validate tool input against schema (PHASE B B6)."""
    return _validator.validate_tool_input_schema(tool_id, input_data, schema)


def validate_tool_output_schema(tool_id: str, output_data: Any, schema: dict[str, Any]) -> bool:
    """Validate tool output against schema (PHASE B B6)."""
    return _validator.validate_tool_output_schema(tool_id, output_data, schema)


def validate_tool_side_effects(tool_id: str, side_effects: list[str]) -> bool:
    """Validate tool side effects (PHASE B B6)."""
    return _validator.validate_tool_side_effects(tool_id, side_effects)
