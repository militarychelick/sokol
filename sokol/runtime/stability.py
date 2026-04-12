"""Stability checker - observational layer for agent behavior consistency."""

from typing import Any
from dataclasses import dataclass

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.stability")


@dataclass
class StabilityReport:
    """Stability assessment report."""

    stability_score: float  # 0.0 - 1.0
    stability_flags: list[str]  # Warnings/detections
    loop_detected: bool = False
    contradiction_detected: bool = False


class StabilityChecker:
    """
    Stability checker - observational layer for agent behavior.

    Responsibilities:
    1. Loop detection (repeated tool calls, repeated intent patterns)
    2. Contradiction detection (conflicting tool calls)
    3. Confidence scoring

    This layer DOES NOT:
    - Block execution
    - Change tool decisions
    - Influence safety layer
    - Modify router output

    It ONLY observes and reports.
    """

    def __init__(self, max_repetitions: int = 3) -> None:
        """
        Initialize stability checker.

        Args:
            max_repetitions: Maximum allowed repetitions before flagging as loop
        """
        self._max_repetitions = max_repetitions
        self._tool_call_history: list[str] = []
        self._intent_pattern_history: list[str] = []

    def evaluate(
        self,
        tool_results: list[Any] | None = None,
        router_output: Any = None,
        memory_context: str = "",
    ) -> StabilityReport:
        """
        Evaluate stability of current execution cycle.

        Args:
            tool_results: List of tool execution results
            router_output: Output from IntentRouter
            memory_context: Memory context string

        Returns:
            StabilityReport with assessment
        """
        flags = []
        loop_detected = False
        contradiction_detected = False

        # Loop detection
        if tool_results:
            loop_detected = self._detect_loops(tool_results)
            if loop_detected:
                flags.append("repetitive_tool_calls")

        # Contradiction detection
        if tool_results and len(tool_results) > 1:
            contradiction_detected = self._detect_contradictions(tool_results)
            if contradiction_detected:
                flags.append("contradictory_tool_calls")

        # Confidence scoring
        confidence = self._compute_confidence(
            tool_results=tool_results,
            router_output=router_output,
            memory_context=memory_context,
        )

        # Adjust stability score based on flags
        stability_score = confidence
        if loop_detected:
            stability_score -= 0.3
        if contradiction_detected:
            stability_score -= 0.2

        # Clamp to 0.0 - 1.0
        stability_score = max(0.0, min(1.0, stability_score))

        return StabilityReport(
            stability_score=stability_score,
            stability_flags=flags,
            loop_detected=loop_detected,
            contradiction_detected=contradiction_detected,
        )

    def _detect_loops(self, tool_results: list[Any]) -> bool:
        """
        Detect repetitive tool calls or intent patterns.

        Args:
            tool_results: List of tool execution results

        Returns:
            True if loop detected
        """
        # Count tool name repetitions
        tool_names = []
        for result in tool_results:
            if hasattr(result, "get"):
                tool_name = result.get("tool_name", "")
            elif hasattr(result, "tool_name"):
                tool_name = result.tool_name
            else:
                continue
            tool_names.append(tool_name)

        # Check for repetitions
        from collections import Counter

        counts = Counter(tool_names)
        for tool_name, count in counts.items():
            if count >= self._max_repetitions:
                logger.warning_data(
                    "Loop detected - repetitive tool calls",
                    {"tool": tool_name, "count": count},
                )
                return True

        return False

    def _detect_contradictions(self, tool_results: list[Any]) -> bool:
        """
        Detect contradictory tool calls.

        Args:
            tool_results: List of tool execution results

        Returns:
            True if contradiction detected
        """
        # Extract tool names and targets
        tool_actions = []
        for result in tool_results:
            if hasattr(result, "get"):
                tool_name = result.get("tool_name", "")
                params = result.get("parameters", {})
            elif hasattr(result, "tool_name"):
                tool_name = result.tool_name
                params = getattr(result, "parameters", {})
            else:
                continue

            # Extract target if available
            target = params.get("path") or params.get("file") or params.get("app") or ""
            tool_actions.append((tool_name, target))

        # Check for contradictory actions on same target
        contradictory_pairs = [
            ("open_file", "delete_file"),
            ("delete_file", "open_file"),
            ("file_write", "file_delete"),
            ("file_delete", "file_write"),
            ("app_launch", "app_close"),
            ("app_close", "app_launch"),
        ]

        for i, (tool1, target1) in enumerate(tool_actions):
            for tool2, target2 in tool_actions[i + 1 :]:
                # Check if same target
                if target1 and target2 and target1 == target2:
                    # Check if contradictory pair
                    if (tool1, tool2) in contradictory_pairs:
                        logger.warning_data(
                            "Contradiction detected - conflicting tool calls",
                            {"tool1": tool1, "tool2": tool2, "target": target1},
                        )
                        return True

        return False

    def _compute_confidence(
        self,
        tool_results: list[Any] | None = None,
        router_output: Any = None,
        memory_context: str = "",
    ) -> float:
        """
        Compute confidence score for current execution.

        Args:
            tool_results: List of tool execution results
            router_output: Output from IntentRouter
            memory_context: Memory context string

        Returns:
            Confidence score (0.0 - 1.0)
        """
        confidence = 1.0

        # Tool failures reduce confidence
        if tool_results:
            failures = 0
            for result in tool_results:
                if hasattr(result, "success") and not result.success:
                    failures += 1
                elif isinstance(result, dict) and not result.get("success", True):
                    failures += 1

            failure_ratio = failures / len(tool_results) if tool_results else 0
            confidence -= failure_ratio * 0.3

        # Memory ambiguity reduces confidence
        if memory_context and "ambiguous" in memory_context.lower():
            confidence -= 0.1

        # Router uncertainty reduces confidence
        if router_output:
            if hasattr(router_output, "source"):
                # Lower confidence for fallback sources
                source = getattr(router_output, "source")
                if hasattr(source, "value") and source.value == "fallback":
                    confidence -= 0.2
            elif isinstance(router_output, dict):
                source = router_output.get("source", "")
                if "fallback" in str(source).lower():
                    confidence -= 0.2

        # Clamp to 0.0 - 1.0
        return max(0.0, min(1.0, confidence))

    def reset(self) -> None:
        """Reset history buffers."""
        self._tool_call_history.clear()
        self._intent_pattern_history.clear()
