"""UX Realness Layer - makes Sokol feel like a continuous assistant."""

from typing import Any, Optional
from dataclasses import dataclass, field

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.ux_realness")


@dataclass
class ExecutionState:
    """Current execution state for UX realness."""

    phase: str = "starting"  # starting, processing, executing_tools, finalizing
    step: Optional[int] = None  # Current step in chain
    total_steps: Optional[int] = None  # Total steps in chain
    tool_name: Optional[str] = None  # Current tool being executed
    context: str = ""  # Brief context for continuity


class UXRealness:
    """
    UX Realness Layer - makes Sokol feel like a continuous assistant.

    This layer:
    - Provides progress awareness for chains
    - Provides execution state hints
    - Maintains continuity across related actions
    - Formats responses to feel natural and progressive

    This layer DOES NOT:
    - Change execution logic
    - Change tool execution
    - Add new execution loops
    - Add state machine
    - Affect router or control logic

    This layer ONLY:
    - Formats presentation
    - Adds progress hints
    - Maintains conversational continuity
    - Makes responses feel natural
    """

    def __init__(self) -> None:
        """Initialize UX Realness layer."""
        self._last_response: str = ""
        self._last_context: str = ""
        self._action_count: int = 0

    def format_with_progress(
        self,
        text: str,
        state: ExecutionState,
        mode: str = "standard",
    ) -> str:
        """
        Format response with progress awareness and state hints.

        Args:
            text: Original response text
            state: Current execution state
            mode: Response mode (compact/standard/detailed)

        Returns:
            Formatted response with progress/state hints
        """
        # Compact mode: no progress hints (keep it short for voice)
        if mode == "compact":
            return text

        # Standard mode: add progress hints for chains
        if mode == "standard":
            return self._format_standard(text, state)

        # Detailed mode: add full state information
        if mode == "detailed":
            return self._format_detailed(text, state)

        return text

    def _format_standard(self, text: str, state: ExecutionState) -> str:
        """
        Format for standard mode - progress hints for chains.

        Args:
            text: Original text
            state: Current execution state

        Returns:
            Text with progress hints
        """
        # Only add progress hints for chains (when we have step/total_steps)
        if state.step is not None and state.total_steps is not None:
            progress_hint = f"Шаг {state.step}/{state.total_steps} выполнен."
            # Prepend progress hint to response
            return f"{progress_hint}\n\n{text}"

        return text

    def _format_detailed(self, text: str, state: ExecutionState) -> str:
        """
        Format for detailed mode - full state information.

        Args:
            text: Original text
            state: Current execution state

        Returns:
            Text with full state information
        """
        state_parts = []

        # Add phase
        phase_map = {
            "starting": "Запуск",
            "processing": "Обработка",
            "executing_tools": "Выполнение инструментов",
            "finalizing": "Завершение",
        }
        phase_text = phase_map.get(state.phase, state.phase)
        state_parts.append(f"Фаза: {phase_text}")

        # Add step progress
        if state.step is not None and state.total_steps is not None:
            state_parts.append(f"Прогресс: {state.step}/{state.total_steps}")

        # Add current tool
        if state.tool_name:
            state_parts.append(f"Инструмент: {state.tool_name}")

        # Add context if available
        if state.context:
            state_parts.append(f"Контекст: {state.context}")

        if state_parts:
            state_text = " | ".join(state_parts)
            return f"[{state_text}]\n\n{text}"

        return text

    def apply_continuity(
        self,
        text: str,
        context: str = "",
    ) -> str:
        """
        Apply continuity layer - reduce redundant explanations.

        Args:
            text: Response text
            context: Current context

        Returns:
            Text with continuity applied
        """
        self._action_count += 1

        # First action: no continuity needed
        if self._action_count == 1:
            self._last_response = text
            self._last_context = context
            return text

        # Check if context is similar to last context
        if self._is_similar_context(context, self._last_context):
            # Reduce redundancy - use shorter, more direct response
            return self._make_incremental(text)

        # Different context: full response
        self._last_response = text
        self._last_context = context
        return text

    def _is_similar_context(self, context1: str, context2: str) -> bool:
        """
        Check if contexts are similar (for continuity).

        Args:
            context1: First context
            context2: Second context

        Returns:
            True if contexts are similar
        """
        if not context1 or not context2:
            return False

        # Simple similarity check: overlap in key words
        words1 = set(context1.lower().split())
        words2 = set(context2.lower().split())

        if not words1 or not words2:
            return False

        # Calculate overlap
        overlap = len(words1 & words2)
        total = len(words1 | words2)

        # If overlap > 50%, consider similar
        return overlap / total > 0.5

    def _make_incremental(self, text: str) -> str:
        """
        Make response more incremental (for continuity).

        Args:
            text: Original text

        Returns:
            Incremental response
        """
        # Add natural transition phrases
        transitions = [
            "Теперь ",
            "Далее ",
            "Следующий шаг: ",
            "Затем ",
        ]

        # If text is long, make it shorter
        if len(text) > 200:
            # Take first sentence and add transition
            sentences = text.split(". ")
            if sentences:
                first_sentence = sentences[0]
                return f"{transitions[0]}{first_sentence}."

        return text

    def create_state(
        self,
        phase: str = "starting",
        step: Optional[int] = None,
        total_steps: Optional[int] = None,
        tool_name: Optional[str] = None,
        context: str = "",
    ) -> ExecutionState:
        """
        Create ExecutionState object.

        Args:
            phase: Execution phase
            step: Current step number
            total_steps: Total steps
            tool_name: Current tool name
            context: Context string

        Returns:
            ExecutionState object
        """
        return ExecutionState(
            phase=phase,
            step=step,
            total_steps=total_steps,
            tool_name=tool_name,
            context=context,
        )

    def reset_continuity(self) -> None:
        """Reset continuity tracking (e.g., on new conversation)."""
        self._last_response = ""
        self._last_context = ""
        self._action_count = 0
