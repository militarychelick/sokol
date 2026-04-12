"""Retry budget for system-level retry policy."""

import time
from typing import Optional
from dataclasses import dataclass, field

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.retry_budget")


@dataclass
class RetryBudget:
    """
    Retry budget for limiting retry attempts.
    
    Prevents infinite retry loops by enforcing:
    - Maximum retries per operation
    - Exponential backoff
    - Per-operation tracking
    """
    
    max_retries: int = 3
    base_delay_ms: float = 100.0
    max_delay_ms: float = 5000.0
    backoff_multiplier: float = 2.0
    
    # Tracking
    _retry_counts: dict[str, int] = field(default_factory=dict)
    _last_retry_time: dict[str, float] = field(default_factory=dict)
    
    def can_retry(self, operation: str) -> tuple[bool, Optional[float]]:
        """
        Check if operation can retry and get delay.
        
        Args:
            operation: Operation identifier (e.g., "tool_execute", "llm_call")
        
        Returns:
            (can_retry, delay_ms) tuple
        """
        retry_count = self._retry_counts.get(operation, 0)
        
        if retry_count >= self.max_retries:
            logger.warning_data(
                "Retry budget exhausted",
                {"operation": operation, "retry_count": retry_count, "max_retries": self.max_retries}
            )
            return False, None
        
        # Calculate delay with exponential backoff
        delay_ms = self.base_delay_ms * (self.backoff_multiplier ** retry_count)
        delay_ms = min(delay_ms, self.max_delay_ms)
        
        return True, delay_ms
    
    def record_attempt(self, operation: str) -> int:
        """
        Record a retry attempt.
        
        Args:
            operation: Operation identifier
        
        Returns:
            Current retry count
        """
        self._retry_counts[operation] = self._retry_counts.get(operation, 0) + 1
        self._last_retry_time[operation] = time.time()
        
        retry_count = self._retry_counts[operation]
        logger.debug_data(
            "Retry attempt recorded",
            {"operation": operation, "retry_count": retry_count}
        )
        
        return retry_count
    
    def reset(self, operation: Optional[str] = None) -> None:
        """
        Reset retry budget.
        
        Args:
            operation: Specific operation to reset, or None to reset all
        """
        if operation:
            self._retry_counts.pop(operation, None)
            self._last_retry_time.pop(operation, None)
            logger.debug_data("Retry budget reset", {"operation": operation})
        else:
            self._retry_counts.clear()
            self._last_retry_time.clear()
            logger.debug("All retry budgets reset")
    
    def get_retry_count(self, operation: str) -> int:
        """
        Get current retry count for operation.
        
        Args:
            operation: Operation identifier
        
        Returns:
            Current retry count
        """
        return self._retry_counts.get(operation, 0)
    
    def is_exhausted(self, operation: str) -> bool:
        """
        Check if retry budget is exhausted for operation.
        
        Args:
            operation: Operation identifier
        
        Returns:
            True if exhausted, False otherwise
        """
        return self._retry_counts.get(operation, 0) >= self.max_retries
