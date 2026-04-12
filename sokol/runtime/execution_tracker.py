"""Execution tracker for Phase 2.3 - Execution feedback loop."""

from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import time


class ExecutionStatus(Enum):
    """Execution status for tracking."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ExecutionResult:
    """Result of event execution."""
    event_type: str
    status: ExecutionStatus
    duration_ms: float
    error_type: Optional[str] = None


class ExecutionTracker:
    """
    Execution tracker for Phase 2.3.
    
    Collects execution metrics WITHOUT influencing decisions directly.
    Metrics are used by SystemState (RecoveryLoop) for closed-loop control.
    
    Separation of concerns:
    - ExecutionTracker: Collects metrics
    - SystemState: Uses metrics to determine state
    - DecisionEngine: Applies rules based on state
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize execution tracker.
        
        Args:
            window_size: Number of recent executions to track
        """
        self._window_size = window_size
        
        # Execution history
        self._execution_history: list[ExecutionResult] = []
        
        # Per-event-type stats
        self._event_stats: Dict[str, Dict] = {}
        
        # Overall stats
        self._total_executions = 0
        self._total_failures = 0
        self._total_timeouts = 0
        self._total_successes = 0
    
    def record_execution(
        self,
        event_type: str,
        status: ExecutionStatus,
        duration_ms: float,
        error_type: Optional[str] = None
    ) -> None:
        """
        Record execution result.
        
        Args:
            event_type: Event type string
            status: Execution status
            duration_ms: Execution duration in milliseconds
            error_type: Optional error type
        """
        result = ExecutionResult(
            event_type=event_type,
            status=status,
            duration_ms=duration_ms,
            error_type=error_type
        )
        
        # Add to history
        self._execution_history.append(result)
        
        # Maintain window size
        if len(self._execution_history) > self._window_size:
            self._execution_history.pop(0)
        
        # Update totals
        self._total_executions += 1
        if status == ExecutionStatus.SUCCESS:
            self._total_successes += 1
        elif status == ExecutionStatus.FAILURE:
            self._total_failures += 1
        elif status == ExecutionStatus.TIMEOUT:
            self._total_timeouts += 1
        
        # Update per-event-type stats
        if event_type not in self._event_stats:
            self._event_stats[event_type] = {
                "total": 0,
                "success": 0,
                "failure": 0,
                "timeout": 0,
                "durations": []
            }
        
        self._event_stats[event_type]["total"] += 1
        if status == ExecutionStatus.SUCCESS:
            self._event_stats[event_type]["success"] += 1
        elif status == ExecutionStatus.FAILURE:
            self._event_stats[event_type]["failure"] += 1
        elif status == ExecutionStatus.TIMEOUT:
            self._event_stats[event_type]["timeout"] += 1
        
        self._event_stats[event_type]["durations"].append(duration_ms)
        if len(self._event_stats[event_type]["durations"]) > self._window_size:
            self._event_stats[event_type]["durations"].pop(0)
    
    def get_failure_rate(self) -> float:
        """
        Get overall failure rate.
        
        Returns:
            Failure rate (0.0-1.0)
        """
        if self._total_executions == 0:
            return 0.0
        return (self._total_failures + self._total_timeouts) / self._total_executions
    
    def get_timeout_rate(self) -> float:
        """
        Get overall timeout rate.
        
        Returns:
            Timeout rate (0.0-1.0)
        """
        if self._total_executions == 0:
            return 0.0
        return self._total_timeouts / self._total_executions
    
    def get_p95_latency(self, event_type: Optional[str] = None) -> float:
        """
        Get p95 execution latency.
        
        Args:
            event_type: Optional event type to filter
        
        Returns:
            p95 latency in milliseconds
        """
        if event_type and event_type in self._event_stats:
            durations = self._event_stats[event_type]["durations"]
        else:
            durations = [r.duration_ms for r in self._execution_history]
        
        if len(durations) == 0:
            return 0.0
        
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)
        return sorted_durations[p95_index] if p95_index < len(sorted_durations) else sorted_durations[-1]
    
    def get_event_type_stats(self, event_type: str) -> Dict:
        """
        Get stats for specific event type.
        
        Args:
            event_type: Event type string
        
        Returns:
            Dictionary with stats
        """
        if event_type not in self._event_stats:
            return {
                "total": 0,
                "success": 0,
                "failure": 0,
                "timeout": 0,
                "failure_rate": 0.0,
                "avg_duration_ms": 0.0
            }
        
        stats = self._event_stats[event_type]
        durations = stats["durations"]
        
        return {
            "total": stats["total"],
            "success": stats["success"],
            "failure": stats["failure"],
            "timeout": stats["timeout"],
            "failure_rate": (stats["failure"] + stats["timeout"]) / stats["total"] if stats["total"] > 0 else 0.0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0
        }
    
    def get_overall_stats(self) -> Dict:
        """
        Get overall execution stats.
        
        Returns:
            Dictionary with overall stats
        """
        return {
            "total_executions": self._total_executions,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_timeouts": self._total_timeouts,
            "failure_rate": self.get_failure_rate(),
            "timeout_rate": self.get_timeout_rate(),
            "p95_latency_ms": self.get_p95_latency()
        }
    
    def reset(self) -> None:
        """Reset all tracking data."""
        self._execution_history.clear()
        self._event_stats.clear()
        self._total_executions = 0
        self._total_failures = 0
        self._total_timeouts = 0
        self._total_successes = 0
