"""Tests for agent state machine."""

import pytest

from sokol.core.types import AgentState
from sokol.runtime.state import AgentStateMachine, StateTransitionError


class TestAgentStateMachine:
    """Tests for AgentStateMachine."""

    def test_initial_state_is_idle(self):
        """Machine starts in IDLE state."""
        sm = AgentStateMachine()
        assert sm.state == AgentState.IDLE

    def test_valid_transition_idle_to_thinking(self):
        """Can transition from IDLE to THINKING."""
        sm = AgentStateMachine()
        assert sm.transition(AgentState.THINKING)
        assert sm.state == AgentState.THINKING

    def test_valid_transition_thinking_to_executing(self):
        """Can transition from THINKING to EXECUTING."""
        sm = AgentStateMachine()
        sm.transition(AgentState.THINKING)
        assert sm.transition(AgentState.EXECUTING)
        assert sm.state == AgentState.EXECUTING

    def test_invalid_transition_idle_to_executing(self):
        """Cannot transition directly from IDLE to EXECUTING."""
        sm = AgentStateMachine()
        assert not sm.can_transition_to(AgentState.EXECUTING)
        assert not sm.transition(AgentState.EXECUTING)
        assert sm.state == AgentState.IDLE

    def test_force_transition_bypasses_validation(self):
        """Force transition bypasses validation."""
        sm = AgentStateMachine()
        sm.force_transition(AgentState.EXECUTING, "test")
        assert sm.state == AgentState.EXECUTING

    def test_reset_returns_to_idle(self):
        """Reset returns to IDLE from any state."""
        sm = AgentStateMachine()
        sm.force_transition(AgentState.ERROR, "test")
        sm.reset()
        assert sm.state == AgentState.IDLE

    def test_is_busy(self):
        """is_busy returns True for non-idle states."""
        sm = AgentStateMachine()
        assert not sm.is_busy()

        sm.transition(AgentState.THINKING)
        assert sm.is_busy()

        sm.transition(AgentState.EXECUTING)
        assert sm.is_busy()

    def test_can_accept_input(self):
        """can_accept_input returns True for IDLE and LISTENING."""
        sm = AgentStateMachine()
        assert sm.can_accept_input()

        sm.transition(AgentState.LISTENING)
        assert sm.can_accept_input()

        sm.transition(AgentState.THINKING)
        assert not sm.can_accept_input()

    def test_previous_state_tracking(self):
        """Tracks previous state on transition."""
        sm = AgentStateMachine()
        sm.transition(AgentState.THINKING)
        assert sm.previous_state == AgentState.IDLE

        sm.transition(AgentState.EXECUTING)
        assert sm.previous_state == AgentState.THINKING

    def test_transition_count(self):
        """Counts transitions."""
        sm = AgentStateMachine()
        assert sm._transition_count == 0

        sm.transition(AgentState.THINKING)
        assert sm._transition_count == 1

        sm.transition(AgentState.EXECUTING)
        assert sm._transition_count == 2

    def test_event_callback(self):
        """Calls event callback on transition."""
        events = []

        def callback(event):
            events.append(event)

        sm = AgentStateMachine()
        sm.set_event_callback(callback)
        sm.transition(AgentState.THINKING)

        assert len(events) == 1
        assert events[0].type.value == "state_change"
        assert events[0].data["from_state"] == "idle"
        assert events[0].data["to_state"] == "thinking"
