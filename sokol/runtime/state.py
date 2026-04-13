"""Agent state machine."""

from sokol.core.constants import STATE_TRANSITIONS
from sokol.core.types import AgentState, AgentEvent, EventType
from sokol.observability.logging import get_logger
from sokol.runtime.result import Result

logger = get_logger("sokol.runtime.state")


class StateTransitionError(Exception):
    """Raised when invalid state transition is attempted."""

    def __init__(self, current: AgentState, target: AgentState) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid state transition: {current.value} -> {target.value}"
        )


class AgentStateMachine:
    """Agent state machine with validation and logging."""

    def __init__(self, initial_state: AgentState = AgentState.IDLE) -> None:
        self._state = initial_state
        self._previous_state: AgentState | None = None
        self._transition_count = 0
        self._event_callback: callable | None = None

    @property
    def state(self) -> AgentState:
        """Current state."""
        return self._state

    @property
    def previous_state(self) -> AgentState | None:
        """Previous state."""
        return self._previous_state

    def can_transition_to(self, target: AgentState) -> Result[bool]:
        """Check if transition to target state is valid."""
        allowed = STATE_TRANSITIONS.get(self._state, [])
        return Result.ok(target in allowed)

    def transition(self, target: AgentState, reason: str = "") -> Result[bool]:
        """
        Attempt to transition to target state.

        Returns True if successful, False if invalid.
        """
        can_transition_result = self.can_transition_to(target)
        if not can_transition_result.is_ok():
            return Result.ok(False)

        if not can_transition_result.unwrap():
            logger.error_data(
                "Invalid state transition attempted",
                {
                    "current": self._state.value,
                    "target": target.value,
                    "reason": reason,
                },
            )
            return Result.ok(False)

        old_state = self._state
        self._previous_state = old_state
        self._state = target
        self._transition_count += 1

        logger.info_data(
            "State transition",
            {
                "from": old_state.value,
                "to": target.value,
                "reason": reason,
                "transition_count": self._transition_count,
            },
        )

        # Emit event if callback is set
        if self._event_callback:
            event = AgentEvent(
                type=EventType.STATE_CHANGE,
                source="state_machine",
                data={
                    "from_state": old_state.value,
                    "to_state": target.value,
                    "reason": reason,
                },
            )
            self._event_callback(event)

        return Result.ok(True)

    def force_transition(self, target: AgentState, reason: str = "") -> None:
        """
        Force transition to target state, bypassing validation.

        Only use for emergency stop or error recovery.
        """
        old_state = self._state
        self._previous_state = old_state
        self._state = target
        self._transition_count += 1

        logger.warning_data(
            "Forced state transition",
            {
                "from": old_state.value,
                "to": target.value,
                "reason": reason,
            },
        )

        if self._event_callback:
            event = AgentEvent(
                type=EventType.STATE_CHANGE,
                source="state_machine",
                data={
                    "from_state": old_state.value,
                    "to_state": target.value,
                    "reason": f"FORCED: {reason}",
                    "forced": True,
                },
            )
            self._event_callback(event)

    def reset(self) -> None:
        """Reset to idle state."""
        self.force_transition(AgentState.IDLE, "reset")

    def set_event_callback(self, callback: callable) -> None:
        """Set callback for state change events."""
        self._event_callback = callback

    def is_busy(self) -> Result[bool]:
        """Check if agent is in a busy state (not idle or listening)."""
        return Result.ok(self._state not in (
            AgentState.IDLE,
            AgentState.LISTENING,
        ))

    def can_accept_input(self) -> Result[bool]:
        """Check if agent can accept user input."""
        return Result.ok(self._state in (
            AgentState.IDLE,
            AgentState.LISTENING,
        ))

    def __repr__(self) -> str:
        return f"AgentStateMachine(state={self._state.value})"
