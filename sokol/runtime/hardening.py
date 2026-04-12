"""System Hardening Layer - runtime invariants and self-checks."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List
from enum import Enum

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.hardening")


class Severity(str, Enum):
    """Severity level for invariant violations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SystemInvariant:
    """System invariant definition."""

    name: str
    check_function: Callable[[], tuple[bool, str]]  # Returns (passed, reason)
    severity: Severity = Severity.MEDIUM


@dataclass
class HardeningViolation:
    """Record of a hardening violation."""

    invariant_name: str
    reason: str
    severity: Severity
    timestamp: str


class HardeningEngine:
    """
    Hardening engine - runtime invariants and self-checks.

    This engine:
    - Registers system invariants
    - Runs pre-execution checks
    - Runs post-execution checks
    - Validates tool results
    - Detects anomalies
    - Logs violations in trace

    This engine DOES NOT:
    - Block execution logic
    - Introduce new decision layer
    - Change router/control/safety behavior
    - Introduce recovery loops

    This engine ONLY:
    - Monitors system state
    - Warns on violations
    - Logs violations
    - Attaches to stability report
    """

    def __init__(self) -> None:
        """Initialize hardening engine."""
        self._invariants: List[SystemInvariant] = []
        self._violations: List[HardeningViolation] = []

        # Register basic invariants
        self._register_basic_invariants()

    def _register_basic_invariants(self) -> None:
        """Register basic system invariants."""
        # Tool result must have success field
        self.register_invariant(
            SystemInvariant(
                name="tool_result_has_success",
                check_function=self._check_tool_result_success,
                severity=Severity.MEDIUM,
            )
        )

        # Stability score must be within 0-1
        self.register_invariant(
            SystemInvariant(
                name="stability_score_range",
                check_function=self._check_stability_score_range,
                severity=Severity.HIGH,
            )
        )

        # Memory size must not exceed limits
        self.register_invariant(
            SystemInvariant(
                name="memory_size_limit",
                check_function=self._check_memory_size_limit,
                severity=Severity.LOW,
            )
        )

        # Tool registry consistency
        self.register_invariant(
            SystemInvariant(
                name="tool_registry_consistency",
                check_function=self._check_tool_registry_consistency,
                severity=Severity.MEDIUM,
            )
        )

        # Control decision must be valid enum
        self.register_invariant(
            SystemInvariant(
                name="control_decision_validity",
                check_function=self._check_control_decision_validity,
                severity=Severity.MEDIUM,
            )
        )

    def register_invariant(self, invariant: SystemInvariant) -> None:
        """
        Register a system invariant.

        Args:
            invariant: SystemInvariant to register
        """
        self._invariants.append(invariant)
        logger.debug_data("Invariant registered", {"name": invariant.name})

    def run_pre_execution_checks(self, context: dict[str, Any] | None = None) -> List[HardeningViolation]:
        """
        Run pre-execution checks.

        Args:
            context: Execution context for checks

        Returns:
            List of violations found
        """
        violations = []

        # Run all invariants
        for invariant in self._invariants:
            try:
                passed, reason = invariant.check_function()
                if not passed:
                    violation = HardeningViolation(
                        invariant_name=invariant.name,
                        reason=reason,
                        severity=invariant.severity,
                        timestamp=self._get_timestamp(),
                    )
                    violations.append(violation)
                    logger.warning_data(
                        "Hardening violation (pre-execution)",
                        {
                            "invariant": invariant.name,
                            "severity": invariant.severity.value,
                            "reason": reason,
                        },
                    )
            except Exception as e:
                logger.error_data(
                    "Invariant check failed",
                    {"invariant": invariant.name, "error": str(e)},
                )

        self._violations.extend(violations)
        return violations

    def run_post_execution_checks(
        self,
        tool_results: List[Any] | None = None,
        stability_score: float = 1.0,
    ) -> List[HardeningViolation]:
        """
        Run post-execution checks.

        Args:
            tool_results: Tool results from execution
            stability_score: Stability score from execution

        Returns:
            List of violations found
        """
        violations = []

        # Validate tool results
        if tool_results:
            for result in tool_results:
                violation = self.validate_tool_result(result)
                if violation:
                    violations.append(violation)

        # Validate stability score
        violation = self.validate_stability_score(stability_score)
        if violation:
            violations.append(violation)

        # Detect anomalies
        anomaly_violations = self.detect_anomalies(tool_results)
        violations.extend(anomaly_violations)

        self._violations.extend(violations)
        return violations

    def validate_tool_result(self, tool_result: Any) -> Optional[HardeningViolation]:
        """
        Validate a single tool result.

        Args:
            tool_result: Tool result to validate

        Returns:
            HardeningViolation if invalid, None otherwise
        """
        if tool_result is None:
            return HardeningViolation(
                invariant_name="tool_result_not_null",
                reason="Tool result is None",
                severity=Severity.HIGH,
                timestamp=self._get_timestamp(),
            )

        # Check for success field
        if not hasattr(tool_result, "success"):
            return HardeningViolation(
                invariant_name="tool_result_has_success",
                reason="Tool result missing 'success' field",
                severity=Severity.MEDIUM,
                timestamp=self._get_timestamp(),
            )

        return None

    def validate_stability_score(self, stability_score: float) -> Optional[HardeningViolation]:
        """
        Validate stability score range.

        Args:
            stability_score: Stability score to validate

        Returns:
            HardeningViolation if invalid, None otherwise
        """
        if not isinstance(stability_score, (int, float)):
            return HardeningViolation(
                invariant_name="stability_score_type",
                reason=f"Stability score must be numeric, got {type(stability_score)}",
                severity=Severity.HIGH,
                timestamp=self._get_timestamp(),
            )

        if stability_score < 0.0 or stability_score > 1.0:
            return HardeningViolation(
                invariant_name="stability_score_range",
                reason=f"Stability score must be within 0-1, got {stability_score}",
                severity=Severity.HIGH,
                timestamp=self._get_timestamp(),
            )

        return None

    def detect_anomalies(self, tool_results: List[Any] | None = None) -> List[HardeningViolation]:
        """
        Detect anomalies in execution.

        Args:
            tool_results: Tool results from execution

        Returns:
            List of violations found
        """
        violations = []

        if not tool_results:
            return violations

        # Check for empty tool chains when chain expected
        if len(tool_results) == 0:
            violations.append(
                HardeningViolation(
                    invariant_name="empty_tool_chain",
                    reason="Tool chain is empty",
                    severity=Severity.MEDIUM,
                    timestamp=self._get_timestamp(),
                )
            )

        return violations

    def get_violations(self) -> List[HardeningViolation]:
        """
        Get all violations recorded.

        Returns:
            List of violations
        """
        return self._violations.copy()

    def clear_violations(self) -> None:
        """Clear all recorded violations."""
        self._violations.clear()

    def _check_tool_result_success(self) -> tuple[bool, str]:
        """Check that tool results have success field (placeholder)."""
        # This is a placeholder - actual check is done in validate_tool_result
        return True, "OK"

    def _check_stability_score_range(self) -> tuple[bool, str]:
        """Check that stability score is within 0-1 (placeholder)."""
        # This is a placeholder - actual check is done in validate_stability_score
        return True, "OK"

    def _check_memory_size_limit(self) -> tuple[bool, str]:
        """Check that memory size does not exceed limits (placeholder)."""
        # This is a placeholder - would check actual memory usage
        return True, "OK"

    def _check_tool_registry_consistency(self) -> tuple[bool, str]:
        """Check that tool registry is consistent (placeholder)."""
        # This is a placeholder - would check tool registry state
        return True, "OK"

    def _check_control_decision_validity(self) -> tuple[bool, str]:
        """Check that control decision is valid enum (placeholder)."""
        # This is a placeholder - would check control decision state
        return True, "OK"

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
