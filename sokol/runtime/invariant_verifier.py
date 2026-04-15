"""Invariant Verifier for Hard Reliability Guarantees.

Checks invariants at runtime boundaries.
Detection-only - no recovery, no state changes.
"""

import time
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from sokol.runtime.bounded_mitigation import EventPriority, SystemState


class InvariantViolationException(Exception):
    """Exception raised when an invariant violation is detected (enforcement mode)."""
    def __init__(self, violation: "InvariantViolation"):
        self.violation = violation
        super().__init__(f"Invariant violation: {violation.invariant_type.value} - {violation.details}")


class InvariantType(Enum):
    """Types of invariants."""
    EMERGENCY_NON_DROP = "emergency_non_drop"
    STATE_TRANSITION_VALIDITY = "state_transition_validity"
    QUEUE_THRESHOLD_ENFORCEMENT = "queue_threshold_enforcement"
    MITIGATION_BYPASS_EXCEPTION = "mitigation_bypass_exception"
    OBSERVER_READ_ONLY = "observer_read_only"


@dataclass
class InvariantViolation:
    """Invariant violation record."""
    invariant_type: InvariantType
    timestamp: float
    details: dict
    severity: str  # "warning", "error"


class InvariantVerifier:
    """
    Invariant Verifier - detection-only verification.
    
    Checks invariants at runtime boundaries.
    Emits violations to observer, does NOT change system state.
    """
    
    def __init__(self):
        """Initialize invariant verifier."""
        self._violations: list[InvariantViolation] = []
        
        # Valid state transitions (static)
        self._valid_transitions = {
            SystemState.NORMAL: [SystemState.THROTTLED],
            SystemState.THROTTLED: [SystemState.NORMAL, SystemState.SAFE, SystemState.DEGRADED],
            SystemState.SAFE: [SystemState.THROTTLED, SystemState.MINIMAL],
            SystemState.MINIMAL: [SystemState.SAFE],
            SystemState.DEGRADED: [SystemState.NORMAL, SystemState.THROTTLED, SystemState.SAFE],
            SystemState.ERROR: [SystemState.NORMAL]  # External restart only
        }
        
        # Queue threshold to state mapping (static)
        self._queue_thresholds = {
            0.95: {SystemState.MINIMAL, SystemState.ERROR},
            0.85: {SystemState.SAFE, SystemState.MINIMAL, SystemState.ERROR},
            0.70: {SystemState.THROTTLED, SystemState.SAFE, SystemState.MINIMAL, SystemState.DEGRADED, SystemState.ERROR}
        }
    
    def verify_emergency_non_drop(
        self,
        event_priority: EventPriority,
        event_dropped: bool,
        system_state: SystemState
    ) -> None:
        """
        Verify I1: Emergency Non-Drop invariant.
        
        Raises InvariantViolationException if invariant is violated.
        
        Args:
            event_priority: Event priority
            event_dropped: Whether event was dropped
            system_state: Current system state
        """
        # Priority 0 must not be dropped if state != ERROR
        if event_priority == EventPriority.EMERGENCY and event_dropped:
            if system_state != SystemState.ERROR:
                violation = InvariantViolation(
                    invariant_type=InvariantType.EMERGENCY_NON_DROP,
                    timestamp=time.time(),
                    details={
                        "priority": event_priority.value,
                        "dropped": event_dropped,
                        "system_state": system_state.name
                    },
                    severity="error"
                )
                self._violations.append(violation)
                raise InvariantViolationException(violation)
    
    def verify_state_transition(
        self,
        old_state: SystemState,
        new_state: SystemState
    ) -> None:
        """
        Verify I2: State Transition Validity invariant.
        
        Raises InvariantViolationException if invariant is violated.
        
        Args:
            old_state: Previous state
            new_state: New state
        """
        valid_next_states = self._valid_transitions.get(old_state, [])
        
        if new_state not in valid_next_states:
            violation = InvariantViolation(
                invariant_type=InvariantType.STATE_TRANSITION_VALIDITY,
                timestamp=time.time(),
                details={
                    "old_state": old_state.name,
                    "new_state": new_state.name,
                    "valid_transitions": [s.name for s in valid_next_states]
                },
                severity="error"
            )
            self._violations.append(violation)
            raise InvariantViolationException(violation)
    
    def verify_queue_threshold(
        self,
        queue_depth: int,
        queue_max: int,
        system_state: SystemState
    ) -> None:
        """
        Verify I3: Queue Threshold Enforcement invariant.
        
        Raises InvariantViolationException if invariant is violated.
        
        Args:
            queue_depth: Current queue depth
            queue_max: Maximum queue size
            system_state: Current system state
        """
        queue_ratio = queue_depth / queue_max
        
        # Check each threshold
        for threshold, allowed_states in self._queue_thresholds.items():
            if queue_ratio > threshold:
                if system_state not in allowed_states:
                    violation = InvariantViolation(
                        invariant_type=InvariantType.QUEUE_THRESHOLD_ENFORCEMENT,
                        timestamp=time.time(),
                        details={
                            "queue_depth": queue_depth,
                            "queue_max": queue_max,
                            "queue_ratio": queue_ratio,
                            "threshold": threshold,
                            "system_state": system_state.name,
                            "allowed_states": [s.name for s in allowed_states]
                        },
                        severity="warning"
                    )
                    self._violations.append(violation)
                    raise InvariantViolationException(violation)
    
    def verify_mitigation_bypass(
        self,
        event_priority: EventPriority,
        mitigation_applied: bool
    ) -> None:
        """
        Verify I4: Mitigation Bypass Exception invariant.
        
        Raises InvariantViolationException if invariant is violated.
        
        Args:
            event_priority: Event priority
            mitigation_applied: Whether mitigation was applied
        """
        # Priority >= 1 must have mitigation applied
        if event_priority != EventPriority.EMERGENCY and not mitigation_applied:
            violation = InvariantViolation(
                invariant_type=InvariantType.MITIGATION_BYPASS_EXCEPTION,
                timestamp=time.time(),
                details={
                    "priority": event_priority.value,
                    "mitigation_applied": mitigation_applied
                },
                severity="error"
            )
            self._violations.append(violation)
            raise InvariantViolationException(violation)
    
    def verify_observer_read_only(
        self,
        decision_source: str,
        system_impact: str
    ) -> None:
        """
        Verify I5: Observer Read-Only invariant.
        
        Raises InvariantViolationException if invariant is violated.
        
        Args:
            decision_source: Source of decision
            system_impact: Impact on system (NONE, STATE_CHANGE, EVENT_DECISION)
        """
        source_str = decision_source or ""
        source = source_str.upper()
        is_observer_source = source == "OBSERVER" or source_str.startswith("observe_")
        if is_observer_source and system_impact != "NONE":
            violation = InvariantViolation(
                invariant_type=InvariantType.OBSERVER_READ_ONLY,
                timestamp=time.time(),
                details={
                    "decision_source": decision_source,
                    "system_impact": system_impact
                },
                severity="error"
            )
            self._violations.append(violation)
            raise InvariantViolationException(violation)
    
    def get_violations(self) -> list[dict]:
        """
        Get all invariant violations.
        
        Returns:
            List of violation dictionaries
        """
        return [
            {
                "type": v.invariant_type.value,
                "timestamp": v.timestamp,
                "details": v.details,
                "severity": v.severity
            }
            for v in self._violations
        ]
    
    def reset(self) -> None:
        """Reset all violations."""
        self._violations.clear()
