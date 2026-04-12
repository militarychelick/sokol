"""Liveness Monitor for Hard Reliability Guarantees.

Monitors system progress and detects starvation.
Detection-only - no recovery, no state changes.
"""

import time
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from sokol.runtime.bounded_mitigation import SystemState


class LivenessType(Enum):
    """Types of liveness checks."""
    EVENT_PROGRESS = "event_progress"
    STATE_TRANSITION_PROGRESS = "state_transition_progress"
    EMERGENCY_STARVATION = "emergency_starvation"


@dataclass
class LivenessViolation:
    """Liveness violation record."""
    liveness_type: LivenessType
    timestamp: float
    details: dict
    severity: str  # "warning", "error"


class LivenessMonitor:
    """
    Liveness Monitor - detection-only monitoring.
    
    Monitors system progress and detects starvation.
    Emits violations to observer, does NOT change system state.
    """
    
    def __init__(self):
        """Initialize liveness monitor."""
        self._violations: list[LivenessViolation] = []
        
        # Tracking
        self._last_event_processed: Optional[float] = None
        self._events_available: bool = False
        self._state_entry_timestamp: Optional[float] = None
        self._transition_needed: bool = False
        self._emergency_submission_timestamp: Optional[float] = None
        self._emergency_execution_timestamp: Optional[float] = None
        
        # Thresholds (static)
        self._event_progress_timeout = 30.0  # seconds
        self._state_transition_timeout = 300.0  # seconds (5 minutes)
        self._emergency_starvation_timeout = 5.0  # seconds
    
    def record_event_processed(self) -> None:
        """Record that an event was processed."""
        self._last_event_processed = time.time()
    
    def set_events_available(self, available: bool) -> None:
        """Set whether events are available."""
        self._events_available = available
    
    def record_state_entry(self, state: SystemState) -> None:
        """Record state entry timestamp."""
        self._state_entry_timestamp = time.time()
    
    def set_transition_needed(self, needed: bool) -> None:
        """Set whether state transition is needed."""
        self._transition_needed = needed
    
    def record_emergency_submission(self) -> None:
        """Record emergency submission timestamp."""
        self._emergency_submission_timestamp = time.time()
    
    def record_emergency_execution(self) -> None:
        """Record emergency execution timestamp."""
        self._emergency_execution_timestamp = time.time()
    
    def verify_event_progress(self, current_state: SystemState) -> Tuple[bool, Optional[LivenessViolation]]:
        """
        Verify L1: Event Progress liveness guarantee.
        
        Args:
            current_state: Current system state
        
        Returns:
            (is_valid, violation) tuple
        """
        # If events are available, system must process at least one event every 30 seconds
        # OR explicitly enter DEGRADED/ERROR state
        if self._events_available and self._last_event_processed is not None:
            time_since_last = time.time() - self._last_event_processed
            if time_since_last > self._event_progress_timeout:
                if current_state not in {SystemState.DEGRADED, SystemState.ERROR}:
                    violation = LivenessViolation(
                        liveness_type=LivenessType.EVENT_PROGRESS,
                        timestamp=time.time(),
                        details={
                            "events_available": self._events_available,
                            "last_processed": self._last_event_processed,
                            "time_since_last": time_since_last,
                            "current_state": current_state.name
                        },
                        severity="error"
                    )
                    self._violations.append(violation)
                    return False, violation
        
        return True, None
    
    def verify_state_transition_progress(self) -> Tuple[bool, Optional[LivenessViolation]]:
        """
        Verify L2: State Transition Progress liveness guarantee.
        
        Returns:
            (is_valid, violation) tuple
        """
        # System must not stay in same state > 5 minutes if metrics indicate need for transition
        if (self._state_entry_timestamp is not None and 
            self._transition_needed and
            self._state_entry_timestamp is not None):
            time_in_state = time.time() - self._state_entry_timestamp
            if time_in_state > self._state_transition_timeout:
                violation = LivenessViolation(
                    liveness_type=LivenessType.STATE_TRANSITION_PROGRESS,
                    timestamp=time.time(),
                    details={
                        "state_entry_timestamp": self._state_entry_timestamp,
                        "time_in_state": time_in_state,
                        "transition_needed": self._transition_needed
                    },
                    severity="error"
                )
                self._violations.append(violation)
                return False, violation
        
        return True, None
    
    def verify_emergency_starvation(self) -> Tuple[bool, Optional[LivenessViolation]]:
        """
        Verify L3: Emergency Starvation liveness guarantee.
        
        Returns:
            (is_valid, violation) tuple
        """
        # Emergency events must not be delayed > 5 seconds
        if (self._emergency_submission_timestamp is not None and 
            self._emergency_execution_timestamp is not None):
            emergency_latency = self._emergency_execution_timestamp - self._emergency_submission_timestamp
            if emergency_latency > self._emergency_starvation_timeout:
                violation = LivenessViolation(
                    liveness_type=LivenessType.EMERGENCY_STARVATION,
                    timestamp=time.time(),
                    details={
                        "submission_timestamp": self._emergency_submission_timestamp,
                        "execution_timestamp": self._emergency_execution_timestamp,
                        "emergency_latency": emergency_latency
                    },
                    severity="error"
                )
                self._violations.append(violation)
                return False, violation
        
        return True, None
    
    def get_violations(self) -> list[dict]:
        """
        Get all liveness violations.
        
        Returns:
            List of violation dictionaries
        """
        return [
            {
                "type": v.liveness_type.value,
                "timestamp": v.timestamp,
                "details": v.details,
                "severity": v.severity
            }
            for v in self._violations
        ]
    
    def reset(self) -> None:
        """Reset all violations and tracking."""
        self._violations.clear()
        self._last_event_processed = None
        self._events_available = False
        self._state_entry_timestamp = None
        self._transition_needed = False
        self._emergency_submission_timestamp = None
        self._emergency_execution_timestamp = None
