"""Response builder for unified output layer."""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from sokol.runtime.result import Result
from sokol.runtime.ux_realness import UXRealness, ExecutionState


class ResponseMode(str, Enum):
    """Response mode for presentation layer."""

    COMPACT = "compact"  # Short, voice-friendly (1-2 sentences)
    STANDARD = "standard"  # Normal UI responses (clear + optional plan)
    DETAILED = "detailed"  # Extended explanations (plan + results + reasoning hints)


@dataclass(frozen=True)
class AgentResponse:
    """Structured response from agent execution (immutable after creation)."""

    user_text: str
    system_log: tuple[dict, ...] = field(default_factory=tuple)
    memory_events: tuple[dict, ...] = field(default_factory=tuple)
    tool_results: tuple[dict, ...] = field(default_factory=tuple)
    success: bool = True
    stability_score: float = 1.0
    stability_flags: tuple[str, ...] = field(default_factory=tuple)
    error: Optional[dict] = None  # Structured error info from errors.ErrorInfo


class ResponseBuilder:
    """
    Response builder - formats results into structured output.

    This class does NOT:
    - Make decisions
    - Route logic
    - Execute tools
    - Access memory directly

    It ONLY:
    - Formats results
    - Builds structured response
    """

    def build(
        self,
        final_text: str,
        tool_results: list[Any] | tuple[Any, ...] | None = None,
        system_logs: list[dict] | tuple[dict, ...] | None = None,
        success: bool = True,
        stability_score: float = 1.0,
        stability_flags: list[str] | tuple[str, ...] | None = None,
        error: Optional[dict] = None,  # Structured error info from errors.ErrorInfo
    ) -> Result[AgentResponse]:
        """
        Build structured response from orchestrator results.

        Args:
            final_text: Text to display to user
            tool_results: List of tool execution results
            system_logs: List of system log entries
            success: Whether execution was successful
            stability_score: Stability score (0.0 - 1.0)
            stability_flags: Stability warning flags

        Returns:
            AgentResponse with structured output
        """
        return Result.ok(
            AgentResponse(
                user_text=final_text,
                system_log=tuple(system_logs or []),  # Copy to tuple for immutability
                memory_events=tuple(),  # Memory events handled separately
                tool_results=tuple(self._format_tool_result(r) for r in (tool_results or [])),  # Create tuple
                success=success,
                stability_score=stability_score,
                stability_flags=tuple(stability_flags or []),  # Copy to tuple for immutability
                error=error,  # Structured error info
            )
        )

    def _format_tool_result(self, result: Any) -> dict:
        """Format tool result for response."""
        if hasattr(result, "model_dump"):
            return result.model_dump()
        elif hasattr(result, "__dict__"):
            return result.__dict__
        else:
            return {"raw": str(result)}


class ResponseFormatter:
    """
    Response formatter - presentation layer for response modes.

    This class does NOT:
    - Change execution logic
    - Change tool execution
    - Change routing or safety

    It ONLY:
    - Formats user_text based on mode
    - Adapts presentation for different contexts (voice, UI, debug)
    """

    def __init__(self) -> None:
        """Initialize response formatter."""
        self._ux_realness = UXRealness()

    def format(
        self,
        response: AgentResponse,
        mode: ResponseMode = ResponseMode.STANDARD,
        state: Optional[ExecutionState] = None,
        context: str = "",
    ) -> Result[AgentResponse]:
        """
        Format response based on mode.

        Args:
            response: AgentResponse to format
            mode: Response mode (compact/standard/detailed)
            state: Optional execution state for UX realness
            context: Optional context for continuity

        Returns:
            AgentResponse with formatted user_text
        """
        formatted_text = self._format_by_mode(
            response.user_text,
            mode,
            response.tool_results,
            response.stability_flags,
        )

        # Apply UX realness layer (progress awareness and continuity)
        if state:
            formatted_text = self._ux_realness.format_with_progress(
                formatted_text,
                state,
                mode.value,
            )

        # Apply continuity layer
        if context:
            formatted_text = self._ux_realness.apply_continuity(
                formatted_text,
                context,
            )

        # Return new response with formatted text (keep other fields unchanged)
        return Result.ok(
            AgentResponse(
                user_text=formatted_text,
                system_log=response.system_log,  # Tuples are immutable, safe to share
                memory_events=response.memory_events,  # Tuples are immutable, safe to share
                tool_results=response.tool_results,  # Tuples are immutable, safe to share
                success=response.success,
                stability_score=response.stability_score,
                stability_flags=response.stability_flags,  # Tuples are immutable, safe to share
                error=response.error,  # Preserve error info
            )
        )

    def _format_by_mode(
        self,
        text: str,
        mode: ResponseMode,
        tool_results: tuple[dict, ...] | None,
        stability_flags: tuple[str, ...] | None,
    ) -> str:
        """
        Format text based on response mode.

        Args:
            text: Original text
            mode: Response mode
            tool_results: Tool execution results
            stability_flags: Stability warning flags

        Returns:
            Formatted text
        """
        if mode == ResponseMode.COMPACT:
            return self._format_compact(text)
        elif mode == ResponseMode.DETAILED:
            return self._format_detailed(text, tool_results, stability_flags)
        else:  # STANDARD
            return self._format_standard(text)

    def _format_compact(self, text: str) -> str:
        """
        Format text for compact mode (voice-friendly, 1-2 sentences).

        Args:
            text: Original text

        Returns:
            Compact text
        """
        # Split into sentences
        sentences = [s.strip() for s in text.split(".") if s.strip()]

        if not sentences:
            return text

        # Return first 1-2 sentences only
        compact_sentences = sentences[:2]
        return ". ".join(compact_sentences) + ("." if compact_sentences else "")

    def _format_standard(self, text: str) -> str:
        """
        Format text for standard mode (clear + optional plan).

        Args:
            text: Original text (may include plan)

        Returns:
            Standard text
        """
        # Standard mode keeps the text as-is (plans already included by PlanGenerator)
        return text

    def _format_detailed(
        self,
        text: str,
        tool_results: tuple[dict, ...] | None,
        stability_flags: tuple[str, ...] | None,
    ) -> str:
        """
        Format text for detailed mode (plan + results + reasoning hints).

        Args:
            text: Original text
            tool_results: Tool execution results
            stability_flags: Stability warning flags

        Returns:
            Detailed text
        """
        detailed_parts = [text]

        # Add tool results summary
        if tool_results:
            results_summary = "\n\nРезультаты выполнения:"
            for i, result in enumerate(tool_results, 1):
                tool_name = result.get("tool", f"Tool {i}")
                # PHASE 6 FIX: Default to False (no silent success)
                success = result.get("success", False)
                status = "✓" if success else "✗"
                results_summary += f"\n{status} {tool_name}"
            detailed_parts.append(results_summary)

        # Add stability information
        if stability_flags:
            stability_info = "\n\nСтабильность: " + ", ".join(stability_flags)
            detailed_parts.append(stability_info)

        return "\n".join(detailed_parts)

    def select_mode(self, source: str, user_bias: Optional[dict[str, Any]] = None) -> ResponseMode:
        """
        Auto-select response mode based on input source and user bias.

        Args:
            source: Input source (voice/ui/debug)
            user_bias: Optional user bias from memory (preferred_mode, etc.)

        Returns:
            ResponseMode enum value
        """
        # Source-based selection (default behavior)
        if source == "voice":
            return ResponseMode.COMPACT
        elif source == "debug":
            return ResponseMode.DETAILED

        # Apply user bias if available (memory influence)
        if user_bias and "preferred_mode" in user_bias:
            preferred = user_bias["preferred_mode"]
            if preferred == "compact":
                return ResponseMode.COMPACT
            elif preferred == "detailed":
                return ResponseMode.DETAILED
            elif preferred == "standard":
                return ResponseMode.STANDARD

        return ResponseMode.STANDARD
