"""Backpressure layer for event pipeline V2."""

import queue
import time
from typing import Tuple


class BackpressureLayer:
    """
    Backpressure signaling layer - does NOT replace queue.
    
    Provides:
    - Queue pressure visibility to input sources
    - Adaptive throttling based on load
    - Graceful degradation signaling
    """
    
    def __init__(self, event_queue: queue.Queue, maxsize: int = 100):
        """
        Initialize backpressure layer.
        
        Args:
            event_queue: The event queue to monitor
            maxsize: Maximum size of the queue
        """
        self._queue = event_queue
        self._maxsize = maxsize
        self._pressure_thresholds = {
            "low": 0.3,      # < 30% full
            "medium": 0.6,   # 30-60% full
            "high": 0.8,     # 60-80% full
            "critical": 0.9   # > 90% full
        }
    
    def get_pressure_level(self) -> str:
        """
        Get current queue pressure level.
        
        Returns:
            Pressure level: "low", "medium", "high", or "critical"
        """
        fill_ratio = self._queue.qsize() / self._maxsize if self._maxsize > 0 else 1.0
        
        if fill_ratio < self._pressure_thresholds["low"]:
            return "low"
        elif fill_ratio < self._pressure_thresholds["medium"]:
            return "medium"
        elif fill_ratio < self._pressure_thresholds["high"]:
            return "high"
        else:
            return "critical"
    
    def get_fill_ratio(self) -> float:
        """
        Get current queue fill ratio.
        
        Returns:
            Fill ratio between 0.0 and 1.0
        """
        return self._queue.qsize() / self._maxsize if self._maxsize > 0 else 1.0
    
    def should_accept_event(self, event_priority: int = 1) -> Tuple[bool, str]:
        """
        Determine if event should be accepted based on pressure.
        
        Args:
            event_priority: Event priority level (0=highest, higher number=lower priority)
        
        Returns:
            (accept, reason) tuple
        """
        pressure = self.get_pressure_level()
        
        # Always accept emergency events
        if event_priority == 0:
            return True, "emergency_priority"
        
        # Reject low-priority events under critical pressure
        if pressure == "critical" and event_priority > 1:
            return False, "queue_critical_pressure"
        
        # Warn but accept under high pressure
        if pressure == "high":
            return True, "queue_high_pressure"
        
        return True, "accept"
    
    def get_throttle_delay_ms(self, source: str) -> int:
        """
        Get adaptive throttle delay for input source.
        
        Higher pressure = longer delay between accepts.
        
        Args:
            source: Input source identifier
        
        Returns:
            Throttle delay in milliseconds
        """
        pressure = self.get_pressure_level()
        
        base_delays = {
            "low": 0,
            "medium": 50,
            "high": 200,
            "critical": 500
        }
        
        return base_delays.get(pressure, 0)
