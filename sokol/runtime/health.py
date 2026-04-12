"""Health check endpoint provider for production observability."""

import time
from typing import Callable, Any, Dict

class HealthChecker:
    """
    Health check endpoint provider.
    
    Provides:
    - /health endpoint
    - Component health status
    - Dependency health checks
    """
    
    def __init__(self):
        """Initialize health checker."""
        self._checks: dict[str, Callable[[], bool]] = {}
        self._check_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Thresholds for alerts
        self._thresholds: Dict[str, float] = {
            "queue_depth_ratio": 0.8,  # Alert when queue > 80% full
            "drop_rate_percent": 10.0,  # Alert when drop rate > 10%
        }
        self._last_alert_time: Dict[str, float] = {}
        self._alert_cooldown: float = 60.0  # Minimum seconds between same alert
    
    def register_check(self, name: str, check: Callable[[], bool]) -> None:
        """
        Register a health check.
        
        Args:
            name: Name of the health check
            check: Function that returns True if healthy, False otherwise
        """
        self._checks[name] = check
    
    def unregister_check(self, name: str) -> bool:
        """
        Unregister a health check.
        
        Args:
            name: Name of the health check to remove
        
        Returns:
            True if check was removed, False if not found
        """
        if name in self._checks:
            del self._checks[name]
            return True
        return False
    
    def get_health_status(self) -> dict[str, Any]:
        """
        Get overall health status.
        
        Returns:
            Dictionary with overall status and individual check results
        """
        results = {}
        overall_healthy = True
        
        for name, check in self._checks.items():
            try:
                healthy = check()
                results[name] = {"healthy": healthy}
                if not healthy:
                    overall_healthy = False
            except Exception as e:
                results[name] = {"healthy": False, "error": str(e)}
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time()
        }
    
    def is_healthy(self) -> bool:
        """
        Check if system is healthy.
        
        Returns:
            True if all checks pass, False otherwise
        """
        status = self.get_health_status()
        return status["status"] == "healthy"
    
    def check_threshold(self, metric_name: str, value: float) -> bool:
        """
        Check if metric exceeds threshold and trigger alert if needed.
        
        Args:
            metric_name: Name of the metric (e.g., "queue_depth_ratio")
            value: Current metric value
        
        Returns:
            True if threshold exceeded, False otherwise
        """
        if metric_name not in self._thresholds:
            return False
        
        threshold = self._thresholds[metric_name]
        
        if value > threshold:
            # Check cooldown
            current_time = time.time()
            last_alert = self._last_alert_time.get(metric_name, 0)
            
            if current_time - last_alert >= self._alert_cooldown:
                self._trigger_alert(metric_name, value, threshold)
                self._last_alert_time[metric_name] = current_time
                return True
        
        return False
    
    def _trigger_alert(self, metric_name: str, value: float, threshold: float) -> None:
        """
        Trigger an alert for threshold violation.
        
        Args:
            metric_name: Name of the metric
            value: Current metric value
            threshold: Threshold value
        """
        from sokol.observability.logging import get_logger
        logger = get_logger("sokol.runtime.health")
        
        logger.warning_data(
            "Threshold alert triggered",
            {
                "metric": metric_name,
                "value": value,
                "threshold": threshold,
                "severity": "warning"
            }
        )
    
    def set_threshold(self, metric_name: str, threshold: float) -> None:
        """
        Set or update a threshold.
        
        Args:
            metric_name: Name of the metric
            threshold: Threshold value
        """
        self._thresholds[metric_name] = threshold
    
    def get_thresholds(self) -> Dict[str, float]:
        """
        Get all configured thresholds.
        
        Returns:
            Dictionary of metric names to threshold values
        """
        return self._thresholds.copy()
