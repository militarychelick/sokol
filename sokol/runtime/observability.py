"""Observability layer - execution tracing and debugging."""

from typing import Any
from dataclasses import dataclass, field
from datetime import datetime

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.observability")


@dataclass
class ExecutionTrace:
    """Execution trace for a single request."""

    trace_id: str
    timestamp: str
    input_text: str
    input_source: str

    # Decisions
    router_decision: dict[str, Any] = field(default_factory=dict)
    control_decision: dict[str, Any] = field(default_factory=dict)

    # Tool execution
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    # Observations
    stability_report: dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""
    recovery_attempts: list[dict[str, Any]] = field(default_factory=list)
    memory_influence: dict[str, Any] = field(default_factory=dict)
    hardening_violations: list[dict[str, Any]] = field(default_factory=list)
    decision_traces: list[dict[str, Any]] = field(default_factory=list)

    # Final output
    final_response: str = ""
    execution_time_seconds: float = 0.0
    success: bool = True
    error: str = ""


class TraceCollector:
    """
    Trace collector - builds execution traces for observability.

    This layer:
    - Collects execution data throughout the pipeline
    - Builds structured traces for debugging
    - Logs traces without affecting execution

    This layer DOES NOT:
    - Change system decisions
    - Change execution order
    - Change pipeline behavior
    - Break runtime on errors
    """

    def __init__(self) -> None:
        """Initialize trace collector."""
        self._current_trace: ExecutionTrace | None = None
        self._start_time: float = 0.0

    def start_trace(self, input_text: str, source: str) -> str:
        """
        Start a new execution trace.

        Args:
            input_text: User input text
            source: Input source

        Returns:
            Trace ID
        """
        import uuid

        trace_id = str(uuid.uuid4())[:8]
        self._current_trace = ExecutionTrace(
            trace_id=trace_id,
            timestamp=datetime.now().isoformat(),
            input_text=input_text,
            input_source=source,
        )
        self._start_time = 0.0  # Will be set when execution starts

        logger.debug_data("Trace started", {"trace_id": trace_id})
        return trace_id

    def record_router_decision(self, decision: Any) -> None:
        """
        Record router decision.

        Args:
            decision: Router decision object
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.router_decision = {
                "action_type": getattr(decision, "action_type", ""),
                "source": getattr(decision, "source", ""),
                "tool": getattr(decision, "tool", ""),
                "confidence": getattr(decision, "confidence", 0.0),
            }
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record router decision", {"error": str(e)})

    def record_control_decision(self, decision: Any) -> None:
        """
        Record control layer decision.

        Args:
            decision: Control layer decision object
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.control_decision = {
                "decision": getattr(decision, "decision", ""),
                "risk_level": getattr(decision, "risk_level", ""),
                "explanation": getattr(decision, "explanation", ""),
            }
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record control decision", {"error": str(e)})

    def record_tool_call(self, tool_name: str, params: dict[str, Any]) -> None:
        """
        Record tool call.

        Args:
            tool_name: Name of tool called
            params: Tool parameters
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.tool_calls.append({
                "tool": tool_name,
                "params": params,
            })
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record tool call", {"error": str(e)})

    def record_tool_result(self, tool_name: str, result: Any) -> None:
        """
        Record tool result.

        Args:
            tool_name: Name of tool
            result: Tool result
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.tool_results.append({
                "tool": tool_name,
                "success": getattr(result, "success", True),
                "data": str(getattr(result, "data", ""))[:200],  # Truncate
            })
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record tool result", {"error": str(e)})

    def record_stability_report(self, report: Any) -> None:
        """
        Record stability report.

        Args:
            report: Stability report object
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.stability_report = {
                "stability_score": getattr(report, "stability_score", 1.0),
                "stability_flags": getattr(report, "stability_flags", []),
                "loop_detected": getattr(report, "loop_detected", False),
                "contradiction_detected": getattr(report, "contradiction_detected", False),
            }
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record stability report", {"error": str(e)})

    def record_memory_context(self, context: str) -> None:
        """
        Record memory context used in execution.

        Args:
            context: Memory context string
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.memory_context = context[:500]  # Truncate
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record memory context", {"error": str(e)})

    def record_memory_influence(self, memory_data: dict[str, Any]) -> None:
        """
        Record memory influence on execution.

        Args:
            memory_data: Memory influence data (user_bias, tool_memory, etc.)
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.memory_influence = memory_data
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record memory influence", {"error": str(e)})

    def record_hardening_violations(self, violations: list[Any]) -> None:
        """
        Record hardening violations in trace.

        Args:
            violations: List of HardeningViolation objects
        """
        if self._current_trace is None:
            return

        try:
            # Convert violations to dict format
            violation_dicts = []
            for v in violations:
                violation_dicts.append({
                    "invariant_name": v.invariant_name,
                    "reason": v.reason,
                    "severity": v.severity.value,
                    "timestamp": v.timestamp,
                })
            self._current_trace.hardening_violations = violation_dicts
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record hardening violations", {"error": str(e)})

    def record_decision_traces(self, decision_traces: list[dict[str, Any]]) -> None:
        """
        Record decision traces in trace.

        Args:
            decision_traces: List of decision trace dictionaries
        """
        if self._current_trace is None:
            return

        try:
            self._current_trace.decision_traces = decision_traces
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record decision traces", {"error": str(e)})

    def record_recovery_attempt(
        self,
        original_tool: str,
        final_tool: str,
        retry_count: int,
        fallback_used: bool,
        success: bool,
    ) -> None:
        """
        Record recovery attempt for tool execution.

        Args:
            original_tool: Original tool name
            final_tool: Final tool name (may be different if fallback used)
            retry_count: Number of retry attempts
            fallback_used: Whether fallback was used
            success: Whether final attempt succeeded
        """
        if self._current_trace is None:
            return

        try:
            recovery_data = {
                "original_tool": original_tool,
                "final_tool": final_tool,
                "retry_count": retry_count,
                "fallback_used": fallback_used,
                "success": success,
            }
            self._current_trace.recovery_attempts.append(recovery_data)
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to record recovery attempt", {"error": str(e)})

    def finalize_trace(self, response: str, success: bool, error: str = "") -> ExecutionTrace | None:
        """
        Finalize and return the execution trace.

        Args:
            response: Final response text
            success: Whether execution was successful
            error: Error message if any

        Returns:
            Completed ExecutionTrace or None
        """
        if self._current_trace is None:
            return None

        try:
            import time

            self._current_trace.final_response = response[:500]  # Truncate
            self._current_trace.success = success
            self._current_trace.error = error
            self._current_trace.execution_time_seconds = time.time() - self._start_time

            trace = self._current_trace
            self._current_trace = None

            return trace
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to finalize trace", {"error": str(e)})
            self._current_trace = None
            return None

    def log_trace(self, trace: ExecutionTrace) -> None:
        """
        Log execution trace.

        Args:
            trace: Execution trace to log
        """
        try:
            logger.info_data(
                "Execution trace",
                {
                    "trace_id": trace.trace_id,
                    "input": trace.input_text[:100],
                    "success": trace.success,
                    "tool_calls": len(trace.tool_calls),
                    "execution_time": trace.execution_time_seconds,
                },
            )
        except Exception as e:
            # Trace errors should not break system
            logger.debug_data("Failed to log trace", {"error": str(e)})

    def start_execution_timer(self) -> None:
        """Start execution timer."""
        import time
        self._start_time = time.time()
