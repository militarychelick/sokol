"""Runtime resilience observer for Hard Reliability Verification.

Pure observation layer only - no control authority, no recommendations.
Output: metrics + logs only.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ObservationType(Enum):
    """Types of observations."""
    STATE_TRANSITION = "state_transition"
    EXECUTION_TRACKING = "execution_tracking"
    CRITICAL_EVENT_DROP = "critical_event_drop"
    EMERGENCY_LATENCY = "emergency_latency"
    EVENT_PROCESSING = "event_processing"


@dataclass
class Observation:
    """Single observation record."""
    observation_type: ObservationType
    timestamp: float
    details: Dict
    severity: str  # "info", "warning", "error"


class ResilienceObserver:
    """
    Pure observation layer for runtime resilience.
    
    Observes system behavior and outputs metrics + logs only.
    No control authority, no recommendations, no enforcement.
    """
    
    def __init__(self):
        """Initialize resilience observer."""
        self._observations: List[Observation] = []
        self._emergency_latencies: List[float] = []
        self._state_transitions: List[Dict] = []
        self._execution_count = 0
        self._tracking_count = 0
    
    def observe_state_transition(
        self,
        old_state: str,
        new_state: str,
        transition_valid: bool
    ) -> None:
        """
        Observe state transition.
        
        Args:
            old_state: Previous state
            new_state: New state
            transition_valid: Whether transition is valid
        """
        observation = Observation(
            observation_type=ObservationType.STATE_TRANSITION,
            timestamp=time.time(),
            details={
                "old_state": old_state,
                "new_state": new_state,
                "valid": transition_valid
            },
            severity="warning" if not transition_valid else "info"
        )
        self._observations.append(observation)
        self._state_transitions.append({
            "timestamp": time.time(),
            "old_state": old_state,
            "new_state": new_state,
            "valid": transition_valid
        })
    
    def observe_execution_tracking(
        self,
        executed_count: int,
        tracked_count: int
    ) -> None:
        """
        Observe execution tracking consistency.
        
        Args:
            executed_count: Number of events executed
            tracked_count: Number of events tracked
        """
        self._execution_count = executed_count
        self._tracking_count = tracked_count
        
        mismatch = executed_count != tracked_count
        observation = Observation(
            observation_type=ObservationType.EXECUTION_TRACKING,
            timestamp=time.time(),
            details={
                "executed_count": executed_count,
                "tracked_count": tracked_count,
                "mismatch": mismatch
            },
            severity="warning" if mismatch else "info"
        )
        self._observations.append(observation)
    
    def observe_critical_event_drop(
        self,
        event_type: str,
        has_reason: bool
    ) -> None:
        """
        Observe critical event drop.
        
        Args:
            event_type: Event type
            has_reason: Whether drop reason was logged
        """
        observation = Observation(
            observation_type=ObservationType.CRITICAL_EVENT_DROP,
            timestamp=time.time(),
            details={
                "event_type": event_type,
                "has_reason": has_reason
            },
            severity="warning" if not has_reason else "info"
        )
        self._observations.append(observation)
    
    def observe_emergency_latency(
        self,
        latency_ms: float
    ) -> None:
        """
        Observe emergency execution latency.
        
        Args:
            latency_ms: Emergency execution latency in milliseconds
        """
        self._emergency_latencies.append(latency_ms)
        
        severity = "info"
        if latency_ms > 5000:
            severity = "error"
        elif latency_ms > 1000:
            severity = "warning"
        
        observation = Observation(
            observation_type=ObservationType.EMERGENCY_LATENCY,
            timestamp=time.time(),
            details={
                "latency_ms": latency_ms
            },
            severity=severity
        )
        self._observations.append(observation)
    
    def observe_event_processing(
        self,
        event_type: str,
        source: str,
        timestamp: float
    ) -> None:
        """
        Observe regular event processing.
        
        Args:
            event_type: Event type string
            source: Event source
            timestamp: Event timestamp
        """
        observation = Observation(
            observation_type=ObservationType.EVENT_PROCESSING,
            timestamp=time.time(),
            details={
                "event_type": event_type,
                "source": source,
                "event_timestamp": timestamp
            },
            severity="info"
        )
        self._observations.append(observation)
    
    def get_observations(self) -> List[Dict]:
        """
        Get all observations.
        
        Returns:
            List of observation dictionaries
        """
        return [
            {
                "type": obs.observation_type.value,
                "timestamp": obs.timestamp,
                "details": obs.details,
                "severity": obs.severity
            }
            for obs in self._observations
        ]
    
    def get_metrics(self) -> Dict:
        """
        Get observation metrics.
        
        Returns:
            Dictionary with metrics
        """
        warning_count = sum(1 for obs in self._observations if obs.severity == "warning")
        error_count = sum(1 for obs in self._observations if obs.severity == "error")
        
        avg_emergency_latency = (
            sum(self._emergency_latencies) / len(self._emergency_latencies)
            if self._emergency_latencies else 0.0
        )
        
        invalid_transitions = sum(
            1 for t in self._state_transitions if not t["valid"]
        )
        
        return {
            "total_observations": len(self._observations),
            "warning_count": warning_count,
            "error_count": error_count,
            "execution_count": self._execution_count,
            "tracking_count": self._tracking_count,
            "tracking_mismatch": self._execution_count != self._tracking_count,
            "avg_emergency_latency_ms": avg_emergency_latency,
            "invalid_state_transitions": invalid_transitions,
            "total_state_transitions": len(self._state_transitions)
        }
    
    def reset(self) -> None:
        """Reset all observations."""
        self._observations.clear()
        self._emergency_latencies.clear()
        self._state_transitions.clear()
        self._execution_count = 0
        self._tracking_count = 0
