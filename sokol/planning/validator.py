"""Plan validation - validate plans before execution."""

from typing import List, Optional
from sokol.planning.plan import Plan, PlanStep
from sokol.core.types import RiskLevel
from sokol.safety.risk import RiskAssessor
from sokol.observability.logging import get_logger

logger = get_logger("sokol.planning.validator")


class PlanValidator:
    """Validate plans before execution."""

    def __init__(self) -> None:
        self._risk_assessor = RiskAssessor()

    def validate(self, plan: Plan) -> tuple[bool, List[str]]:
        """
        Validate a plan.

        Returns (is_valid, errors) tuple.
        """
        errors = []

        # Check if plan has steps
        if not plan.steps:
            errors.append("Plan has no steps")
            return False, errors

        # Validate each step
        for step in plan.steps:
            step_errors = self._validate_step(step)
            errors.extend(step_errors)

        # Validate step dependencies
        dep_errors = self._validate_dependencies(plan)
        errors.extend(dep_errors)

        # Check for circular dependencies
        circular_errors = self._check_circular_dependencies(plan)
        errors.extend(circular_errors)

        is_valid = len(errors) == 0

        if is_valid:
            logger.info_data("Plan validation passed", {"plan_id": plan.id})
        else:
            logger.warning_data(
                "Plan validation failed",
                {"plan_id": plan.id, "errors": errors},
            )

        return is_valid, errors

    def _validate_step(self, step: PlanStep) -> List[str]:
        """Validate a single step."""
        errors = []

        # Check step ID
        if not step.id:
            errors.append(f"Step has no ID: {step.description}")

        # Check description
        if not step.description:
            errors.append(f"Step {step.id} has no description")

        # Check action type
        if step.action_type not in ("tool_call", "final_answer", "clarification"):
            errors.append(
                f"Step {step.id} has invalid action_type: {step.action_type}"
            )

        # For tool_call, check tool is specified
        if step.action_type == "tool_call" and not step.tool:
            errors.append(f"Step {step.id} is tool_call but no tool specified")

        # Validate tool risk
        if step.tool:
            risk_level = self._risk_assessor.assess_tool(step.tool, step.args)
            if risk_level == RiskLevel.DANGEROUS:
                # Not an error, but log warning
                logger.warning_data(
                    "Step has dangerous tool",
                    {"step_id": step.id, "tool": step.tool, "risk": risk_level.value},
                )

        return errors

    def _validate_dependencies(self, plan: Plan) -> List[str]:
        """Validate step dependencies."""
        errors = []
        step_ids = {step.id for step in plan.steps}

        for step in plan.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    errors.append(
                        f"Step {step.id} depends on non-existent step: {dep_id}"
                    )

        return errors

    def _check_circular_dependencies(self, plan: Plan) -> List[str]:
        """Check for circular dependencies in the plan."""
        errors = []

        # Build dependency graph
        graph = {step.id: step.depends_on for step in plan.steps}

        # Check for cycles using DFS
        visited = set()
        recursion_stack = set()

        def has_cycle(step_id: str) -> bool:
            if step_id in recursion_stack:
                return True
            if step_id in visited:
                return False

            visited.add(step_id)
            recursion_stack.add(step_id)

            for dep_id in graph.get(step_id, []):
                if has_cycle(dep_id):
                    return True

            recursion_stack.remove(step_id)
            return False

        for step_id in graph:
            if has_cycle(step_id):
                errors.append(f"Circular dependency detected involving step: {step_id}")
                break

        return errors

    def estimate_execution_time(self, plan: Plan) -> float:
        """
        Estimate total execution time for the plan.

        Returns estimated time in seconds.
        """
        # Simple heuristic: 2 seconds per step
        base_time = len(plan.steps) * 2.0

        # Add extra time for dangerous operations
        for step in plan.steps:
            if step.tool:
                risk_level = self._risk_assessor.assess_tool(step.tool, step.args)
                if risk_level == RiskLevel.DANGEROUS:
                    base_time += 5.0  # Extra time for confirmation

        return base_time

    def get_risk_summary(self, plan: Plan) -> dict[str, int]:
        """
        Get risk summary for the plan.

        Returns counts of each risk level.
        """
        risk_counts = {
            "read": 0,
            "write": 0,
            "dangerous": 0,
            "unknown": 0,
        }

        for step in plan.steps:
            if step.tool:
                risk_level = self._risk_assessor.assess_tool(step.tool, step.args)
                risk_counts[risk_level.value] += 1
            else:
                risk_counts["unknown"] += 1

        return risk_counts
