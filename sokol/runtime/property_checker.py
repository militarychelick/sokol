"""Property Checker for Hard Reliability Guarantees.

Checks chaos-resistance properties.
Detection-only - no recovery, no state changes.
"""

import time
from typing import Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass

from sokol.runtime.bounded_mitigation import EventPriority, SystemState


class PropertyViolationException(Exception):
    """Exception raised when a property violation is detected (enforcement mode)."""
    def __init__(self, violation: "PropertyViolation"):
        self.violation = violation
        super().__init__(f"Property violation: {violation.property_type.value} - {violation.details}")


class PropertyType(Enum):
    """Types of properties."""
    PRIORITY_ORDERING = "priority_ordering"
    MITIGATION_APPLICATION = "mitigation_application"
    OBSERVER_NON_INTERFERENCE = "observer_non_interference"
    EMERGENCY_BYPASS = "emergency_bypass"
    STATE_CONVERGENCE = "state_convergence"


@dataclass
class PropertyViolation:
    """Property violation record."""
    property_type: PropertyType
    timestamp: float
    details: dict
    severity: str  # "warning", "error"


class PropertyChecker:
    """
    Property Checker - detection-only checking.
    
    Checks chaos-resistance properties.
    Emits violations to observer, does NOT change system state.
    """
    
    def __init__(self):
        """Initialize property checker."""
        self._violations: list[PropertyViolation] = []
        
        # Valid states (static)
        self._valid_states = {
            SystemState.NORMAL,
            SystemState.THROTTLED,
            SystemState.SAFE,
            SystemState.MINIMAL,
            SystemState.DEGRADED,
            SystemState.ERROR
        }
    
    def check_priority_ordering(self, event_queue: List[dict]) -> None:
        """
        Check P1: Priority Ordering property.
        
        Raises PropertyViolationException if property is violated.
        
        Args:
            event_queue: List of events in queue with priorities
        """
        # Priority ordering always respected (0 > 1 > 2 > 3 > 4)
        # Check if any lower priority event is processed before higher priority
        for i in range(len(event_queue) - 1):
            current_priority = event_queue[i].get("priority", 4)
            next_priority = event_queue[i + 1].get("priority", 4)
            if current_priority > next_priority:
                violation = PropertyViolation(
                    property_type=PropertyType.PRIORITY_ORDERING,
                    timestamp=time.time(),
                    details={
                        "current_priority": current_priority,
                        "next_priority": next_priority,
                        "position": i
                    },
                    severity="error"
                )
                self._violations.append(violation)
                raise PropertyViolationException(violation)
    
    def check_mitigation_application(
        self,
        event_priority: EventPriority,
        mitigation_applied: bool
    ) -> None:
        """
        Check P2: Mitigation Application property.
        
        Raises PropertyViolationException if property is violated.
        
        Args:
            event_priority: Event priority
            mitigation_applied: Whether mitigation was applied
        """
        # Mitigation layer always applied for priority >= 2
        if event_priority in [EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]:
            if not mitigation_applied:
                violation = PropertyViolation(
                    property_type=PropertyType.MITIGATION_APPLICATION,
                    timestamp=time.time(),
                    details={
                        "priority": event_priority.value,
                        "mitigation_applied": mitigation_applied
                    },
                    severity="error"
                )
                self._violations.append(violation)
                raise PropertyViolationException(violation)
    
    def check_observer_non_interference(
        self,
        observer_signals: List[dict]
    ) -> None:
        """
        Check P3: Observer Non-Interference property.
        
        Raises PropertyViolationException if property is violated.
        
        Args:
            observer_signals: List of observer signals
        """
        # Observer never affects execution flow
        for signal in observer_signals:
            if signal.get("execution_impact") != "NONE":
                violation = PropertyViolation(
                    property_type=PropertyType.OBSERVER_NON_INTERFERENCE,
                    timestamp=time.time(),
                    details={
                        "signal": signal
                    },
                    severity="error"
                )
                self._violations.append(violation)
                raise PropertyViolationException(violation)
    
    def check_emergency_bypass(
        self,
        event_priority: EventPriority,
        mitigation_applied: bool
    ) -> None:
        """
        Check P4: Emergency Bypass property.
        
        Raises PropertyViolationException if property is violated.
        
        Args:
            event_priority: Event priority
            mitigation_applied: Whether mitigation was applied
        """
        # Emergency events always bypass mitigation
        if event_priority == EventPriority.EMERGENCY:
            if mitigation_applied:
                violation = PropertyViolation(
                    property_type=PropertyType.EMERGENCY_BYPASS,
                    timestamp=time.time(),
                    details={
                        "priority": event_priority.value,
                        "mitigation_applied": mitigation_applied
                    },
                    severity="error"
                )
                self._violations.append(violation)
                raise PropertyViolationException(violation)
    
    def check_state_convergence(self, system_state: SystemState) -> None:
        """
        Check P5: State Convergence property.
        
        Raises PropertyViolationException if property is violated.
        
        Args:
            system_state: Current system state
        """
        # System always in valid state set
        if system_state not in self._valid_states:
            violation = PropertyViolation(
                property_type=PropertyType.STATE_CONVERGENCE,
                timestamp=time.time(),
                details={
                    "system_state": system_state.name,
                    "valid_states": [s.name for s in self._valid_states]
                },
                severity="error"
            )
            self._violations.append(violation)
            raise PropertyViolationException(violation)
    
    def get_violations(self) -> list[dict]:
        """
        Get all property violations.
        
        Returns:
            List of violation dictionaries
        """
        return [
            {
                "type": v.property_type.value,
                "timestamp": v.timestamp,
                "details": v.details,
                "severity": v.severity
            }
            for v in self._violations
        ]
    
    def reset(self) -> None:
        """Reset all violations."""
        self._violations.clear()
