"""Agent state machine.

State Model Architecture (STRICT NORMALIZATION):

Two State Layers (Mathematically Separated):

1. Execution State (Temporary):
   - During pipeline execution
   - Intermediate states (THINKING, EXECUTING, WAITING_CONFIRM)
   - Can have intermediate commits for error recovery
   - NOT final until commit_state()

2. Committed State (Final):
   - After commit_state() call
   - Reflects completed execution only
   - Single final commit point per execution
   - Cannot be rolled back

Safety Model (NOT a State Layer):
- Safety = Interrupt → Abort Pipeline → No Commit
- Emergency stop: interrupt execution, cancel tasks, NO state mutation
- Watchdog: monitor for stuck states, cancel tasks, NO state mutation
- Safety does NOT use rollback_state() or state transitions
- State mutation ONLY through commit_state()
"""

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
        self._event_result_channel: callable | None = None
        self._staged_state: AgentState | None = None
        self._staged_reason: str = ""
        self._staged_forced: bool = False

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

        if not can_transition_result.value:
            logger.error_data(
                "Invalid state transition attempted",
                {
                    "current": self._state.value,
                    "target": target.value,
                    "reason": reason,
                },
            )
            return Result.ok(False)

        self._staged_state = target
        self._staged_reason = reason
        self._staged_forced = False
        return self.commit_state(Result.ok(True))

    def force_transition(self, target: AgentState, reason: str = "") -> Result[bool]:
        """
        Force transition to target state, bypassing validation.

        Only use for emergency stop or error recovery.
        PHASE A: Added Result wrapper for CORE INVARIANT "state = reality".

        Returns:
            Result[bool] - True if successful
        """
        self._staged_state = target
        self._staged_reason = reason
        self._staged_forced = True
        return self.commit_state(Result.ok(True))

    def reset(self) -> Result[bool]:
        """
        Reset to idle state.
        PHASE A: Added Result wrapper for CORE INVARIANT "state = reality".

        Returns:
            Result[bool] - True if successful
        """
        return self.force_transition(AgentState.IDLE, "reset")

    def set_event_callback(self, callback: callable) -> None:
        """
        Set callback for state change events.
        PHASE A: Bridge mode - will be removed in PHASE C.
        """
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

    def commit_state(self, result) -> Result[bool]:
        """
        Commit state based on execution result.

        This is the ONLY function that can change state in the execution kernel.
        State commit happens exactly once per execution, AFTER execution, BEFORE response.

        Args:
            result: Execution result (Result[AgentResponse] or error result)

        Returns:
            Result[bool] - True if state committed, False if error (no commit on error)
        """
        # PHASE A: State commit point definition
        # TODO: In PHASE B, enforce that only this function can change state
        # TODO: In PHASE B, add validation that no direct state mutation occurred

        if not hasattr(result, 'is_ok') or not result.is_ok():
            # Error result - do NOT commit state
            self._staged_state = None
            self._staged_reason = ""
            self._staged_forced = False
            logger.warning_data(
                "State commit skipped due to error",
                {"error": str(result.error) if hasattr(result, 'error') else "unknown"}
            )
            return Result.ok(False)

        # Success result - commit staged transition if present
        if self._staged_state is not None:
            self._apply_committed_state(
                target=self._staged_state,
                reason=self._staged_reason,
                forced=self._staged_forced,
            )
            self._staged_state = None
            self._staged_reason = ""
            self._staged_forced = False

        logger.info_data(
            "State commit",
            {
                "current_state": self._state.value,
                "transition_count": self._transition_count,
            }
        )

        return Result.ok(True)

    def _apply_committed_state(self, target: AgentState, reason: str = "", forced: bool = False) -> None:
        """Apply a staged state transition at the mutation gate."""
        old_state = self._state
        self._previous_state = old_state
        self._state = target
        self._transition_count += 1

        log_data = {
            "from": old_state.value,
            "to": target.value,
            "reason": reason,
            "transition_count": self._transition_count,
        }
        if forced:
            logger.warning_data("Forced state transition", log_data)
        else:
            logger.info_data("State transition", log_data)

        if self._event_callback:
            event_data = {
                "from_state": old_state.value,
                "to_state": target.value,
                "reason": f"FORCED: {reason}" if forced else reason,
            }
            if forced:
                event_data["forced"] = True
            event = AgentEvent(
                type=EventType.STATE_CHANGE,
                source="state_machine",
                data=event_data,
            )
            self._event_callback(event)
