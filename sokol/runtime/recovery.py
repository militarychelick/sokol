"""Failure recovery - controlled retry and fallback for tool execution."""

from typing import Any, Callable

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.recovery")


class FailureRecovery:
    """
    Failure recovery - controlled retry and fallback for tool execution.

    This class:
    - Provides controlled retry mechanism (max 1 retry on failure)
    - Provides fallback mechanism using ToolIntelligenceEngine
    - Does NOT add new execution loops
    - Does NOT add async systems
    - Does NOT add planners
    - Does NOT use recursion
    - Does NOT mutate global state

    Recovery is:
    - Controlled (max 1 retry, 1 fallback)
    - Minimal (only on failure)
    - Observable (logged in tool_results and trace)
    - Integrated (affects stability_score)
    """

    def __init__(self) -> None:
        """Initialize failure recovery."""
        self._max_retries = 1  # Max 1 retry (2 attempts total)
        self._min_fallback_confidence = 0.3  # Minimum confidence for fallback

    def execute_with_recovery(
        self,
        tool_name: str,
        params: dict[str, Any],
        execute_func: Callable[[str, dict[str, Any]], Any],
        tool_intelligence_engine: Any,
        intent: str,
        context: str,
        stability_score: float,
    ) -> tuple[Any, dict[str, Any]]:
        """
        Execute tool with retry and fallback recovery.

        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            execute_func: Function to execute tool (signature: tool_name, params -> result)
            tool_intelligence_engine: ToolIntelligenceEngine instance
            intent: User intent for fallback selection
            context: Context for fallback selection
            stability_score: Current stability score

        Returns:
            Tuple of (tool_result, recovery_info)
            recovery_info contains: retry_count, fallback_used, final_tool
        """
        recovery_info = {
            "retry_count": 0,
            "fallback_used": False,
            "final_tool": tool_name,
            "attempts": [],
        }

        # First attempt
        result = execute_func(tool_name, params)
        recovery_info["attempts"].append({
            "tool": tool_name,
            "success": getattr(result, "success", False),  # Default to False - cannot assume success
            "error": getattr(result, "error", None),
        })

        # If success, return immediately
        if getattr(result, "success", False):
            return result, recovery_info

        # Retry mechanism (max 1 retry)
        if recovery_info["retry_count"] < self._max_retries:
            logger.info_data(
                "Tool execution failed, retrying",
                {"tool": tool_name, "error": getattr(result, "error", "Unknown")},
            )

            recovery_info["retry_count"] += 1
            result = execute_func(tool_name, params)
            recovery_info["attempts"].append({
                "tool": tool_name,
                "success": getattr(result, "success", False),  # Default to False - cannot assume success
                "error": getattr(result, "error", None),
            })

            # If retry succeeded, return
            if getattr(result, "success", False):
                return result, recovery_info

        # Fallback mechanism
        # Get available tools from intelligence engine
        all_tools = tool_intelligence_engine.get_available_tools() if hasattr(tool_intelligence_engine, "get_available_tools") else []

        # Rank tools for fallback (exclude the failed tool)
        fallback_candidates = [t for t in all_tools if t != tool_name]

        if fallback_candidates:
            ranked_tools = tool_intelligence_engine.rank_tools(
                tools=fallback_candidates,
                intent=intent,
                context=context,
                stability_score=stability_score,
            )

            # Select best fallback if confidence is high enough
            if ranked_tools:
                best_fallback = tool_intelligence_engine.select_best_tool(
                    ranked_tools,
                    fallback_tool=None,  # No fallback for fallback
                )

                # Check confidence
                fallback_confidence = 0.0
                for tool_data in ranked_tools:
                    if tool_data.get("tool") == best_fallback:
                        fallback_confidence = tool_data.get("score", 0.0)
                        break

                if fallback_confidence >= self._min_fallback_confidence:
                    logger.info_data(
                        "Attempting fallback tool",
                        {
                            "original": tool_name,
                            "fallback": best_fallback,
                            "confidence": fallback_confidence,
                        },
                    )

                    # Execute fallback
                    result = execute_func(best_fallback, params)
                    recovery_info["fallback_used"] = True
                    recovery_info["final_tool"] = best_fallback
                    recovery_info["attempts"].append({
                        "tool": best_fallback,
                        "success": getattr(result, "success", False),  # Default to False - cannot assume success
                        "error": getattr(result, "error", None),
                    })

                    return result, recovery_info

        # All recovery attempts failed
        logger.warning_data(
            "All recovery attempts failed",
            {
                "original_tool": tool_name,
                "retry_count": recovery_info["retry_count"],
                "fallback_used": recovery_info["fallback_used"],
            },
        )

        return result, recovery_info

    def get_stability_penalty(self, recovery_info: dict[str, Any]) -> float:
        """
        Calculate stability penalty based on recovery attempts.

        Args:
            recovery_info: Recovery information from execute_with_recovery

        Returns:
            Stability penalty (0.0 - 1.0)
        """
        penalty = 0.0

        # Penalty for retry
        if recovery_info["retry_count"] > 0:
            penalty += 0.1

        # Penalty for fallback
        if recovery_info["fallback_used"]:
            penalty += 0.2

        # Penalty for failed attempts - default to False for success (strict)
        failed_attempts = sum(1 for attempt in recovery_info["attempts"] if not attempt.get("success", False))
        penalty += failed_attempts * 0.05

        return min(penalty, 0.5)  # Cap at 0.5

    def format_failure_message(self, tool_name: str, recovery_info: dict[str, Any]) -> str:
        """
        Format user-friendly failure message.

        Args:
            tool_name: Original tool name
            recovery_info: Recovery information

        Returns:
            User-friendly failure message (no internal errors)
        """
        if recovery_info["fallback_used"]:
            return f"Не удалось выполнить {tool_name}, попробовал альтернативу."
        elif recovery_info["retry_count"] > 0:
            return f"Не удалось выполнить {tool_name} после повторной попытки."
        else:
            return f"Не удалось выполнить {tool_name}."
