"""User Model - personalized behavioral model for Sokol."""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.user_model")


class RiskTolerance(str, Enum):
    """User risk tolerance level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class UserProfile:
    """User profile with preferences and patterns."""

    # Response preferences
    response_mode: str = "standard"  # compact/standard/detailed
    verbosity: str = "normal"  # terse/normal/verbose
    style: str = "professional"  # professional/casual/technical

    # Tool success preferences (which tools work well for this user)
    tool_success_preferences: dict[str, float] = field(default_factory=dict)

    # Interaction patterns
    voice_usage_frequency: int = 0  # Count of voice interactions
    ui_usage_frequency: int = 0  # Count of UI interactions
    total_interactions: int = 0  # Total interaction count

    # Risk tolerance
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM

    # Compressed history summary
    history_summary: str = ""

    # Timestamps
    last_interaction: Optional[str] = None


class UserModel:
    """
    User Model - personalized behavioral model.

    This model:
    - Tracks user preferences and patterns
    - Updates from interactions
    - Provides context bias for presentation
    - Summarizes history for memory

    This model DOES NOT:
    - Change execution logic
    - Change tool execution
    - Change router or control logic
    - Introduce autonomy
    """

    def __init__(self) -> None:
        """Initialize user model."""
        self._profile = UserProfile()
        self._interaction_buffer: list[dict[str, Any]] = []  # Short-term buffer
        self._buffer_size = 10  # Keep last 10 interactions for context

    def update_from_interaction(
        self,
        source: str,
        mode: str,
        tool_used: Optional[str] = None,
        tool_success: bool = True,
        risk_level: Optional[str] = None,
    ) -> None:
        """
        Update user model from interaction.

        Args:
            source: Interaction source (voice/ui)
            mode: Response mode used
            tool_used: Tool name if any
            tool_success: Whether tool execution succeeded
            risk_level: Risk level of action
        """
        # Update interaction counts
        self._profile.total_interactions += 1

        if source == "voice":
            self._profile.voice_usage_frequency += 1
        else:
            self._profile.ui_usage_frequency += 1

        # Update response mode preference (moving average)
        current_preference = self._profile.response_mode
        # Simple preference tracking: if user consistently uses one mode
        self._profile.response_mode = mode

        # Update tool success preferences
        if tool_used:
            current_score = self._profile.tool_success_preferences.get(tool_used, 0.5)
            # Moving average: new score = 0.7 * old + 0.3 * result
            new_score = 0.7 * current_score + 0.3 * (1.0 if tool_success else 0.0)
            self._profile.tool_success_preferences[tool_used] = new_score

        # Update risk tolerance based on approvals
        if risk_level:
            if risk_level == "dangerous":
                # If user approved dangerous actions, increase tolerance
                if self._profile.risk_tolerance == RiskTolerance.LOW:
                    self._profile.risk_tolerance = RiskTolerance.MEDIUM
                elif self._profile.risk_tolerance == RiskTolerance.MEDIUM:
                    self._profile.risk_tolerance = RiskTolerance.HIGH

        # Add to interaction buffer
        interaction = {
            "source": source,
            "mode": mode,
            "tool_used": tool_used,
            "tool_success": tool_success,
            "risk_level": risk_level,
        }
        self._interaction_buffer.append(interaction)

        # Maintain buffer size
        if len(self._interaction_buffer) > self._buffer_size:
            self._interaction_buffer.pop(0)

        logger.debug_data(
            "User model updated",
            {
                "total_interactions": self._profile.total_interactions,
                "voice_usage": self._profile.voice_usage_frequency,
                "ui_usage": self._profile.ui_usage_frequency,
            },
        )

    def get_preferences(self) -> UserProfile:
        """
        Get user profile preferences.

        Returns:
            UserProfile with current preferences
        """
        return self._profile

    def infer_context_bias(self) -> dict[str, Any]:
        """
        Infer context bias for presentation.

        Returns:
            Dictionary with bias hints (response_mode, verbosity, etc.)
        """
        bias = {}

        # Response mode bias
        # If user prefers voice, default to compact
        voice_ratio = 0.0
        if self._profile.total_interactions > 0:
            voice_ratio = self._profile.voice_usage_frequency / self._profile.total_interactions

        if voice_ratio > 0.7:
            bias["preferred_mode"] = "compact"
        elif voice_ratio < 0.3:
            bias["preferred_mode"] = "standard"
        else:
            bias["preferred_mode"] = self._profile.response_mode

        # Verbosity bias
        if self._profile.verbosity == "verbose":
            bias["verbosity_boost"] = 1.2
        elif self._profile.verbosity == "terse":
            bias["verbosity_boost"] = 0.8
        else:
            bias["verbosity_boost"] = 1.0

        # Tool success bias (for tool intelligence)
        bias["tool_success_scores"] = self._profile.tool_success_preferences.copy()

        # Risk tolerance bias
        bias["risk_tolerance"] = self._profile.risk_tolerance.value

        return bias

    def summarize_history(self) -> str:
        """
        Summarize interaction history.

        Returns:
            Compressed history summary
        """
        if not self._interaction_buffer:
            return "No interaction history."

        summary_parts = []

        # Total interactions
        summary_parts.append(f"Всего взаимодействий: {self._profile.total_interactions}")

        # Voice vs UI ratio
        voice_ratio = 0.0
        if self._profile.total_interactions > 0:
            voice_ratio = self._profile.voice_usage_frequency / self._profile.total_interactions

        if voice_ratio > 0.7:
            summary_parts.append("Предпочитает голосовой ввод")
        elif voice_ratio < 0.3:
            summary_parts.append("Предпочитает текстовый ввод")
        else:
            summary_parts.append("Смешанный ввод")

        # Risk tolerance
        summary_parts.append(f"Толерантность к риску: {self._profile.risk_tolerance.value}")

        # Recent tool usage
        if self._profile.tool_success_preferences:
            top_tools = sorted(
                self._profile.tool_success_preferences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            tool_str = ", ".join([f"{tool} ({score:.2f})" for tool, score in top_tools])
            summary_parts.append(f"Успешные инструменты: {tool_str}")

        return ". ".join(summary_parts)

    def get_tool_success_score(self, tool_name: str) -> float:
        """
        Get success score for a specific tool.

        Args:
            tool_name: Tool name

        Returns:
            Success score (0.0 - 1.0)
        """
        return self._profile.tool_success_preferences.get(tool_name, 0.5)

    def get_interaction_buffer(self) -> list[dict[str, Any]]:
        """
        Get interaction buffer for context retrieval.

        Returns:
            List of recent interactions
        """
        return self._interaction_buffer.copy()
