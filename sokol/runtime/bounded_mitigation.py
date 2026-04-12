"""Bounded Mitigation Layer for production runtime.

Implements bounded protection per Hard Priority Preemption Contract.
No decision logic, no recovery, only local protective actions.
"""

import time
from typing import Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class EventPriority(Enum):
    """Event priority levels (static, immutable)."""
    EMERGENCY = 0  # Absolute preemption
    CRITICAL = 1   # High preemption
    HIGH = 2       # Standard preemption
    NORMAL = 3     # No preemption
    LOW = 4        # Deferred


class SystemState(Enum):
    """System recovery states."""
    NORMAL = 0      # Full functionality
    THROTTLED = 1   # Reduced rates, background paused
    SAFE = 2        # Critical sources only
    MINIMAL = 3     # Emergency only
    DEGRADED = 4    # Functional but limited capacity
    ERROR = 5       # Terminal local state


@dataclass
class MitigationResult:
    """Result of mitigation check."""
    allowed: bool
    reason: str
    priority: EventPriority


class BoundedMitigationLayer:
    """
    Bounded Mitigation Layer - local protective actions only.
    
    Per Hard Priority Preemption Contract:
    - Priority 0 (EMERGENCY): Always passes, no mitigation
    - Priority 1 (CRITICAL): Bypasses rate limiting, subject to queue
    - Priority 2+ (HIGH/NORMAL/LOW): Subject to all mitigation
    """
    
    def __init__(self):
        """Initialize bounded mitigation layer."""
        # Rate limiting per source
        self._source_rates: Dict[str, float] = {}
        self._source_last_accept: Dict[str, float] = {}
        
        # Static rate limits (events per second)
        self._rate_limits = {
            SystemState.NORMAL: 10.0,
            SystemState.THROTTLED: 5.0,
            SystemState.SAFE: 2.0,
            SystemState.MINIMAL: 0.0,
            SystemState.DEGRADED: 3.0,
            SystemState.ERROR: 0.0
        }
        
        # State-based priority acceptance
        self._state_acceptance = {
            SystemState.NORMAL: [EventPriority.EMERGENCY, EventPriority.CRITICAL, 
                               EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW],
            SystemState.THROTTLED: [EventPriority.EMERGENCY, EventPriority.CRITICAL,
                                    EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW],  # TEMPORARY: Allow all
            SystemState.SAFE: [EventPriority.EMERGENCY, EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW],  # TEMPORARY: Allow all
            SystemState.MINIMAL: [EventPriority.EMERGENCY, EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW],  # TEMPORARY: Allow all
            SystemState.DEGRADED: [EventPriority.EMERGENCY, EventPriority.CRITICAL,
                                   EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW],  # TEMPORARY: Allow all
            SystemState.ERROR: [EventPriority.EMERGENCY, EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]  # TEMPORARY: Allow all
        }
    
    def check_event(
        self,
        priority: EventPriority,
        source: str,
        system_state: SystemState,
        queue_depth: int,
        queue_max: int = 100
    ) -> MitigationResult:
        """
        Check if event should be allowed through mitigation.
        
        TEMPORARILY DISABLED: Always allow events.
        
        Args:
            priority: Event priority
            source: Event source
            system_state: Current system state
            queue_depth: Current queue depth
            queue_max: Maximum queue size
        
        Returns:
            MitigationResult with decision
        """
        # TEMPORARILY DISABLED: Always allow all events
        return MitigationResult(
            allowed=True,
            reason="bypassed_temporarily",
            priority=priority
        )
    
    def _check_rate_limit(self, source: str, system_state: SystemState) -> bool:
        """
        Check if source is within rate limit.
        
        Args:
            source: Event source
            system_state: Current system state
        
        Returns:
            True if within rate limit
        """
        rate_limit = self._rate_limits.get(system_state, 0.0)
        if rate_limit == 0.0:
            return False
        
        current_time = time.time()
        last_accept = self._source_last_accept.get(source, 0.0)
        
        # Calculate time since last accept
        time_since = current_time - last_accept
        min_interval = 1.0 / rate_limit
        
        if time_since >= min_interval:
            self._source_last_accept[source] = current_time
            return True
        
        return False
    
    def get_metrics(self) -> Dict:
        """
        Get mitigation metrics.
        
        Returns:
            Dictionary with metrics
        """
        return {
            "active_sources": len(self._source_last_accept),
            "source_last_accept": self._source_last_accept.copy()
        }
