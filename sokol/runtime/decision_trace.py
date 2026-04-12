"""Decision Trace Layer - structured reasoning metadata about system decisions."""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from enum import Enum
from datetime import datetime
import time

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.decision_trace")


class DecisionType(str, Enum):
    """Decision type for trace."""

    TOOL_SELECTION = "tool_selection"
    RISK_ASSESSMENT = "risk_assessment"
    TASK_CONTINUATION = "task_continuation"
    RECOVERY_DECISION = "recovery_decision"
    RESPONSE_MODE_SELECTION = "response_mode_selection"
    TOOL_REGISTRY_RESOLUTION = "tool_registry_resolution"


@dataclass
class DecisionTrace:
    """Structured decision trace object."""

    trace_id: str
    decision_type: DecisionType
    input_context: dict[str, Any]
    options_considered: List[str]
    selected_option: str
    confidence_score: float  # 0-1
    influencing_factors: List[str]
    memory_influence: Optional[dict[str, Any]] = None
    tool_history_influence: Optional[dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)


class DecisionTraceCollector:
    """
    Decision trace collector - stores and manages decision traces.

    This collector:
    - Records decision traces
    - Maintains trace chains per request
    - Provides trace summaries
    - Supports trace retrieval

    This collector DOES NOT:
    - Change execution logic
    - Modify routing decisions
    - Modify tool selection behavior
    - Introduce new control decisions
    - Add async processing
    - Add agent autonomy
    - Replace observability system

    This collector ONLY:
    - Records decision metadata
    - Explains decisions
    - Maintains trace chains
    """

    def __init__(self) -> None:
        """Initialize decision trace collector."""
        self._decision_traces: dict[str, List[DecisionTrace]] = {}  # trace_id -> list of decisions
        self._execution_chains: dict[str, List[str]] = {}  # execution_id -> list of trace_ids

    def record_decision(self, decision: DecisionTrace, execution_id: Optional[str] = None) -> None:
        """
        Record a decision trace.

        Args:
            decision: DecisionTrace to record
            execution_id: Optional execution ID for chain tracking
        """
        # Add to decision traces
        if decision.trace_id not in self._decision_traces:
            self._decision_traces[decision.trace_id] = []
        self._decision_traces[decision.trace_id].append(decision)

        # Add to execution chain if provided
        if execution_id:
            if execution_id not in self._execution_chains:
                self._execution_chains[execution_id] = []
            if decision.trace_id not in self._execution_chains[execution_id]:
                self._execution_chains[execution_id].append(decision.trace_id)

        logger.debug_data(
            "Decision trace recorded",
            {
                "trace_id": decision.trace_id,
                "decision_type": decision.decision_type.value,
                "selected_option": decision.selected_option,
                "confidence": decision.confidence_score,
            },
        )

    def get_trace(self, trace_id: str) -> List[DecisionTrace]:
        """
        Get decision trace by ID.

        Args:
            trace_id: Trace ID

        Returns:
            List of DecisionTrace objects
        """
        return self._decision_traces.get(trace_id, [])

    def get_execution_trace_chain(self, execution_id: str) -> List[DecisionTrace]:
        """
        Get all decision traces for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            List of all DecisionTrace objects for the execution
        """
        trace_ids = self._execution_chains.get(execution_id, [])
        all_traces = []

        for trace_id in trace_ids:
            traces = self._decision_traces.get(trace_id, [])
            all_traces.extend(traces)

        return all_traces

    def summarize_decisions(self, execution_id: str) -> dict[str, Any]:
        """
        Summarize decisions for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            Summary dictionary
        """
        traces = self.get_execution_trace_chain(execution_id)

        summary = {
            "total_decisions": len(traces),
            "decision_types": {},
            "average_confidence": 0.0,
            "decisions_by_type": {},
        }

        if not traces:
            return summary

        confidence_sum = 0.0

        for trace in traces:
            decision_type = trace.decision_type.value
            summary["decision_types"][decision_type] = summary["decision_types"].get(decision_type, 0) + 1

            confidence_sum += trace.confidence_score

            if decision_type not in summary["decisions_by_type"]:
                summary["decisions_by_type"][decision_type] = []

            summary["decisions_by_type"][decision_type].append({
                "selected_option": trace.selected_option,
                "confidence": trace.confidence_score,
                "influencing_factors": trace.influencing_factors,
            })

        summary["average_confidence"] = confidence_sum / len(traces) if traces else 0.0

        return summary

    def clear_execution_chain(self, execution_id: str) -> None:
        """
        Clear decision traces for an execution.

        Args:
            execution_id: Execution ID
        """
        trace_ids = self._execution_chains.get(execution_id, [])

        for trace_id in trace_ids:
            if trace_id in self._decision_traces:
                del self._decision_traces[trace_id]

        if execution_id in self._execution_chains:
            del self._execution_chains[execution_id]

        logger.debug_data(
            "Execution decision chain cleared",
            {"execution_id": execution_id},
        )

    def generate_trace_id(self) -> str:
        """
        Generate unique trace ID.

        Returns:
            Unique trace ID
        """
        import uuid
        return f"decision_trace_{uuid.uuid4().hex[:8]}"
