"""Planning Light - lightweight plan generation for transparency."""

from typing import Any

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.planning")


class PlanGenerator:
    """
    Plan generator - creates lightweight action plans for transparency.

    This layer:
    - Generates plans before execution
    - Provides user understanding of what will happen
    - Does NOT control execution
    - Does NOT change decisions

    This layer DOES NOT:
    - Add planner engine
    - Add multi-step reasoning loops
    - Add task decomposition
    - Change orchestrator loop
    - Change tool execution
    - Change router decisions
    """

    def generate_plan(
        self,
        action: Any,
        control_result: Any | None = None,
        verbosity_boost: float = 1.0,
    ) -> str:
        """
        Generate a plan for the proposed action.

        Args:
            action: ProposedAction (tool or tool_chain)
            control_result: Control layer result (optional)
            verbosity_boost: Multiplier for plan verbosity (from memory)

        Returns:
            Text description of the plan
        """
        # Check if action has tool_chain
        if hasattr(action, "tool_chain") and action.tool_chain:
            return self._generate_chain_plan(action.tool_chain)

        # Check if single tool
        elif action.action_type == "tool_call":
            return self._generate_tool_plan(action, control_result)

        else:
            # Non-tool actions (final_answer, clarification) - no plan needed
            return ""

    def _generate_chain_plan(self, chain: Any) -> str:
        """
        Generate plan for tool chain.

        Args:
            chain: ToolChain

        Returns:
            Text description of chain plan
        """
        if not chain or not chain.steps:
            return ""

        plan_lines = ["План выполнения:"]
        for i, step in enumerate(chain.steps):
            step_num = i + 1
            tool_name = step.tool

            # Generate human-readable step description
            step_desc = self._get_tool_description(tool_name, step.params)
            plan_lines.append(f"{step_num}. {step_desc}")

        return "\n".join(plan_lines)

    def _generate_tool_plan(self, action: Any, control_result: Any | None = None) -> str:
        """
        Generate plan for single tool action.

        Args:
            action: ProposedAction with tool
            control_result: Control layer result

        Returns:
            Text description of tool plan
        """
        tool_name = action.tool or ""
        params = action.args or {}

        # Only generate plan for medium/high risk tools
        if control_result and control_result.risk_level:
            risk = control_result.risk_level.value
            if risk in ["medium", "high"]:
                desc = self._get_tool_description(tool_name, params)
                return f"План выполнения:\n1. {desc}"

        return ""

    def _get_tool_description(self, tool_name: str, params: dict[str, Any]) -> str:
        """
        Get human-readable description for a tool.

        Args:
            tool_name: Name of tool
            params: Tool parameters

        Returns:
            Human-readable description
        """
        tool_lower = tool_name.lower()

        # Common tool descriptions
        if "file" in tool_lower:
            if "read" in tool_lower:
                return f"Прочитать файл: {params.get('path', '')}"
            elif "write" in tool_lower or "create" in tool_lower:
                return f"Записать в файл: {params.get('path', '')}"
            elif "delete" in tool_lower:
                return f"Удалить файл: {params.get('path', '')}"
            else:
                return f"Операция с файлом: {params.get('path', '')}"

        elif "app" in tool_lower or "launch" in tool_lower:
            app_name = params.get("app_name", params.get("name", ""))
            return f"Запустить приложение: {app_name}"

        elif "system" in tool_lower:
            if "info" in tool_lower:
                return "Получить информацию о системе"
            else:
                return "Системная операция"

        elif "process" in tool_lower:
            if "kill" in tool_lower:
                pid = params.get("pid", "")
                return f"Завершить процесс: {pid}"
            else:
                return "Операция с процессами"

        else:
            # Generic description
            return f"Выполнить: {tool_name}"
