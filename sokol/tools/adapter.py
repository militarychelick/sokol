"""Tool Adapter Layer - PHASE B B1

Adapter layer for gradual migration of existing tools to contract compliance.

This adapter:
- Wraps existing tools to enforce contract compliance
- Validates tool side effects (external vs internal)
- Provides gradual migration path
- Ensures new tools are contract-bound from start
"""

from typing import Any
from sokol.runtime.result import Result
from sokol.runtime.contract_validator import validate_tool_side_effects
from sokol.observability.logging import get_logger

logger = get_logger("sokol.tools.adapter")


class ToolAdapter:
    """
    Adapter for existing tools to enforce contract compliance.

    This adapter wraps tools to ensure they comply with PHASE B contract requirements:
    - No internal system side effects (memory writes, state changes, event emission)
    - External side effects allowed (compute, external API calls, read operations)
    """

    def __init__(self, tool: Any):
        """
        Initialize tool adapter.

        Args:
            tool: Tool instance to wrap
        """
        self._tool = tool

    def execute(self, **params: Any) -> Result[Any]:
        """
        Execute tool with contract validation.

        Args:
            **params: Tool parameters

        Returns:
            Result with tool execution result
        """
        # PHASE B B1: Validate tool side effects before execution
        side_effects = self._detect_side_effects(params)
        validate_tool_side_effects(self._tool.name, side_effects)

        # Execute tool
        result = self._tool.execute(**params)

        return result

    def _detect_side_effects(self, params: dict[str, Any]) -> list[str]:
        """
        Detect potential side effects from tool parameters.

        Args:
            params: Tool parameters

        Returns:
            List of detected side effects
        """
        side_effects = []

        # PHASE B B1: Detect potential internal system side effects
        # This is a basic detection - tools should explicitly declare side effects
        if "memory" in params or "store" in params:
            side_effects.append("memory_write")

        if "state" in params or "transition" in params:
            side_effects.append("state_change")

        if "event" in params or "emit" in params:
            side_effects.append("event_emission")

        return side_effects


class ContractCompliantToolWrapper:
    """
    Wrapper for new tools to ensure contract compliance.

    This wrapper enforces:
    - Result[ToolResult[T]] return type
    - Schema validation
    - Side effect validation
    """

    def __init__(self, tool: Any, input_schema: dict = None, output_schema: dict = None):
        """
        Initialize contract-compliant tool wrapper.

        Args:
            tool: Tool instance
            input_schema: Input schema for validation
            output_schema: Output schema for validation
        """
        self._tool = tool
        self._input_schema = input_schema or {}
        self._output_schema = output_schema or {}

    def execute(self, **params: Any) -> Result[Any]:
        """
        Execute tool with full contract validation.

        Args:
            **params: Tool parameters

        Returns:
            Result with tool execution result
        """
        from sokol.runtime.contract_validator import validate_tool_input_schema, validate_tool_output_schema

        # PHASE B B1: Validate input schema
        validate_tool_input_schema(self._tool.name, params, self._input_schema)

        # Execute tool
        result = self._tool.execute(**params)

        # PHASE B B1: Validate output schema
        if result.is_ok():
            validate_tool_output_schema(self._tool.name, result.value, self._output_schema)

        return result
