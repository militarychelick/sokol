"""Control Layer - risk assessment and confirmation logic."""

import threading
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.control")


class RiskLevel(str, Enum):
    """Risk level for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ControlDecision(str, Enum):
    """Control decision for action execution."""

    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCKED = "blocked"


@dataclass
class ControlResult:
    """Result of control layer evaluation."""

    decision: ControlDecision
    risk_level: RiskLevel
    explanation: str
    plan_preview: list[str] | None = None  # For chains: list of step descriptions


class ControlLayer:
    """
    Control layer - risk assessment and confirmation logic.

    This layer:
    - Assesses risk of proposed actions
    - Decides if confirmation is required
    - Provides plan preview for high-risk actions
    - Supports emergency stop

    This layer DOES NOT:
    - Change execution logic
    - Change tool execution
    - Block tools (only requests confirmation)
    """

    def __init__(self, tool_registry: Optional[Any] = None, require_confirmation_medium: bool = False, task_manager: Optional[Any] = None) -> None:
        """
        Initialize control layer.

        Args:
            tool_registry: Optional ToolRegistry for risk refinement by category
            require_confirmation_medium: Whether to require confirmation for medium risk
            task_manager: Optional TaskManager for task risk assessment
        """
        self._lock = threading.RLock()
        self._tool_registry = tool_registry
        self._require_confirmation_medium = require_confirmation_medium
        self._task_manager = task_manager
        self._emergency_stop_triggered = False

    def evaluate(
        self,
        action: Any,
        context: str = "",
        tool_metadata: dict[str, Any] | None = None,
    ) -> ControlResult:
        """
        Evaluate action for risk and determine control decision.

        Args:
            action: ProposedAction (tool or tool_chain)
            context: Request context
            tool_metadata: Tool metadata if available

        Returns:
            ControlResult with decision and explanation
        """
        # Check emergency stop first (highest priority)
        with self._lock:
            emergency_triggered = self._emergency_stop_triggered
        
        if emergency_triggered:
            logger.warning("Emergency stop triggered, blocking action")
            return ControlResult(
                decision=ControlDecision.BLOCKED,
                risk_level=RiskLevel.HIGH,
                explanation="Emergency stop triggered",
            )

        # Check if action has tool_chain
        if hasattr(action, "tool_chain") and action.tool_chain:
            return self._evaluate_chain(action.tool_chain, context, tool_metadata)
        elif action.action_type == "tool_call":
            result = self._evaluate_tool(action, context, tool_metadata)

            # Apply tool registry risk refinement (category-based adjustment)
            if self._tool_registry and action.tool:
                category = self._tool_registry.get_tool_category(action.tool)
                if category == "filesystem" and result.risk_level == RiskLevel.MEDIUM:
                    # Filesystem tools are higher risk by default
                    result = ControlResult(
                        decision=result.decision,
                        risk_level=RiskLevel.HIGH,
                        explanation=f"{result.explanation} (filesystem category risk adjustment)",
                        plan_preview=result.plan_preview,
                    )
                elif category == "network" and result.risk_level == RiskLevel.LOW:
                    # Network tools are at least medium risk
                    result = ControlResult(
                        decision=result.decision,
                        risk_level=RiskLevel.MEDIUM,
                        explanation=f"{result.explanation} (network category risk adjustment)",
                        plan_preview=result.plan_preview,
                    )

            # Apply task risk assessment (if task_manager is available)
            if self._task_manager:
                active_task = self._task_manager.get_active_task()
                if active_task and active_task.risk_level == "high":
                    # High-risk task requires confirmation
                    if result.decision == ControlDecision.ALLOW:
                        result = ControlResult(
                            decision=ControlDecision.REQUIRE_CONFIRMATION,
                            risk_level=RiskLevel.HIGH,
                            explanation=f"{result.explanation} (high-risk task requires confirmation)",
                            plan_preview=result.plan_preview,
                        )

            return result
        else:
            # Non-tool actions (final_answer, clarification) - always allow
            return ControlResult(
                decision=ControlDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                explanation="Non-tool action",
            )

    def _evaluate_tool(
        self,
        action: Any,
        context: str,
        tool_metadata: dict[str, Any] | None,
    ) -> ControlResult:
        """
        Evaluate single tool action.

        Args:
            action: ProposedAction with tool
            context: Request context
            tool_metadata: Tool metadata

        Returns:
            ControlResult with decision
        """
        tool_name = action.tool or ""

        # Get risk level from metadata or heuristic
        risk_level = self._assess_tool_risk(tool_name, tool_metadata)

        # Determine decision based on risk level
        if risk_level == RiskLevel.HIGH:
            decision = ControlDecision.REQUIRE_CONFIRMATION
            explanation = f"High risk action: {tool_name}"
        elif risk_level == RiskLevel.MEDIUM and self._require_confirmation_medium:
            decision = ControlDecision.REQUIRE_CONFIRMATION
            explanation = f"Medium risk action: {tool_name}"
        else:
            decision = ControlDecision.ALLOW
            explanation = f"Low risk action: {tool_name}"

        logger.info_data(
            "Control layer decision",
            {"tool": tool_name, "decision": decision.value, "risk": risk_level.value},
        )

        return ControlResult(
            decision=decision,
            risk_level=risk_level,
            explanation=explanation,
        )

    def _evaluate_chain(
        self,
        chain: Any,
        context: str,
        tool_metadata: dict[str, Any] | None,
    ) -> ControlResult:
        """
        Evaluate tool chain.

        Args:
            chain: ToolChain
            context: Request context
            tool_metadata: Tool metadata

        Returns:
            ControlResult with decision and plan preview
        """
        # Assess overall chain risk
        chain_risk = self._assess_chain_risk(chain, tool_metadata)

        # Build plan preview
        plan_preview = []
        for i, step in enumerate(chain.steps):
            step_risk = self._assess_tool_risk(step.tool, tool_metadata)
            plan_preview.append(
                f"Step {i+1}: {step.tool} (risk: {step_risk.value})"
            )

        # Determine decision based on overall risk
        if chain_risk == RiskLevel.HIGH:
            decision = ControlDecision.REQUIRE_CONFIRMATION
            explanation = f"High risk chain with {chain.step_count} steps"
        elif chain_risk == RiskLevel.MEDIUM and self._require_confirmation_medium:
            decision = ControlDecision.REQUIRE_CONFIRMATION
            explanation = f"Medium risk chain with {chain.step_count} steps"
        else:
            decision = ControlDecision.ALLOW
            explanation = f"Low risk chain with {chain.step_count} steps"

        logger.info_data(
            "Control layer decision for chain",
            {"steps": chain.step_count, "decision": decision.value, "risk": chain_risk.value},
        )

        return ControlResult(
            decision=decision,
            risk_level=chain_risk,
            explanation=explanation,
            plan_preview=plan_preview,
        )

    def _assess_tool_risk(self, tool_name: str, tool_metadata: dict[str, Any] | None) -> RiskLevel:
        """
        Assess risk level for a tool.

        Args:
            tool_name: Name of tool
            tool_metadata: Tool metadata if available

        Returns:
            RiskLevel
        """
        # Check metadata first
        if tool_metadata:
            metadata_risk = tool_metadata.get("risk_level")
            if metadata_risk:
                try:
                    return RiskLevel(metadata_risk.lower())
                except ValueError:
                    pass

        # Heuristic risk assessment
        high_risk_keywords = ["delete", "remove", "format", "wipe", "kill", "terminate"]
        medium_risk_keywords = ["write", "modify", "change", "update", "install", "launch"]

        tool_lower = tool_name.lower()

        if any(keyword in tool_lower for keyword in high_risk_keywords):
            return RiskLevel.HIGH
        elif any(keyword in tool_lower for keyword in medium_risk_keywords):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _assess_chain_risk(self, chain: Any, tool_metadata: dict[str, Any] | None) -> RiskLevel:
        """
        Assess overall risk level for a chain.

        Args:
            chain: ToolChain
            tool_metadata: Tool metadata

        Returns:
            RiskLevel (highest risk among steps)
        """
        max_risk = RiskLevel.LOW

        for step in chain.steps:
            step_risk = self._assess_tool_risk(step.tool, tool_metadata)
            if step_risk == RiskLevel.HIGH:
                return RiskLevel.HIGH
            elif step_risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM

        return max_risk

    def trigger_emergency_stop(self, reason: str = "") -> None:
        """
        Trigger emergency stop.

        Args:
            reason: Reason for emergency stop
        """
        self._emergency_stop_triggered = True
        # Sync with global emergency handler
        from sokol.safety.emergency import get_emergency_handler
        global_handler = get_emergency_handler()
        if not global_handler.is_triggered():
            global_handler.trigger(reason=f"control_layer: {reason}")
        logger.warning_data("Emergency stop triggered", {"reason": reason})

    def clear_emergency_stop(self) -> None:
        """Clear emergency stop flag."""
        self._emergency_stop_triggered = False
        # Sync with global emergency handler
        from sokol.safety.emergency import get_emergency_handler
        global_handler = get_emergency_handler()
        global_handler.reset()
        logger.info("Emergency stop cleared")

    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is active."""
        return self._emergency_stop_triggered
