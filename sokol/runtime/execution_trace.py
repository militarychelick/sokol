"""Execution Trace System - PHASE B B3

Execution trace collector for full replayability.

This system:
- Captures execution nodes for replayability
- Passive journal (does NOT participate in decision making)
- Does NOT influence execution flow
- Minimal structure: id, input, action, output, result
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from datetime import datetime
import uuid

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.execution_trace")


@dataclass
class ExecutionNode:
    """
    Execution node for trace replayability (PHASE B B3).

    Minimal structure to avoid "VM inside VM" risk:
    - id: Unique identifier
    - input: Input to this node
    - action: Action performed
    - output: Output from this node
    - result: Result status

    This node is PASSIVE - does NOT participate in decision making,
    does NOT influence execution flow.
    """
    id: str
    input: dict[str, Any]
    action: str
    output: Any
    result: str  # "success" or "error"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExecutionTrace:
    """
    Execution trace collector (PHASE B B3).

    This collector:
    - Stores execution nodes in memory
    - Append-only (no modifications)
    - Passive journal for replayability only
    - Does NOT participate in decision making
    - Does NOT influence execution flow
    """

    def __init__(self, max_nodes: int = 1000):
        """
        Initialize execution trace collector.

        Args:
            max_nodes: Maximum number of nodes to keep in memory
        """
        self._nodes: List[ExecutionNode] = []
        self._max_nodes = max_nodes
        self._maintenance_mode = False

    def add_node(self, input_data: dict[str, Any], action: str, output: Any, result: str) -> str:
        """
        Add execution node to trace.

        Args:
            input_data: Input to this node
            action: Action performed
            output: Output from this node
            result: Result status ("success" or "error")

        Returns:
            Node ID
        """
        node = ExecutionNode(
            id=str(uuid.uuid4()),
            input=input_data,
            action=action,
            output=output,
            result=result,
        )

        self._nodes.append(node)

        # Maintain max nodes (append-only, remove oldest)
        if len(self._nodes) > self._max_nodes:
            self._nodes.pop(0)

        logger.debug_data(
            "Execution node added to trace",
            {
                "node_id": node.id,
                "action": action,
                "result": result,
                "total_nodes": len(self._nodes),
            },
        )

        return node.id

    def get_nodes(self) -> List[ExecutionNode]:
        """
        Get all execution nodes.

        Returns:
            List of execution nodes (read-only)
        """
        return self._nodes.copy()

    def clear(self) -> None:
        """Clear all execution nodes."""
        if not self._maintenance_mode:
            logger.warning("Execution trace clear blocked (maintenance mode disabled)")
            return
        self._nodes.clear()
        logger.debug("Execution trace cleared")

    def get_stats(self) -> dict[str, Any]:
        """
        Get trace statistics.

        Returns:
            Dictionary with trace stats
        """
        return {
            "total_nodes": len(self._nodes),
            "max_nodes": self._max_nodes,
            "success_count": sum(1 for node in self._nodes if node.result == "success"),
            "error_count": sum(1 for node in self._nodes if node.result == "error"),
        }


# Global trace instance
_global_trace: Optional[ExecutionTrace] = None


def get_execution_trace() -> ExecutionTrace:
    """
    Get global execution trace instance.

    Returns:
        ExecutionTrace instance
    """
    global _global_trace
    if _global_trace is None:
        _global_trace = ExecutionTrace()
    return _global_trace
