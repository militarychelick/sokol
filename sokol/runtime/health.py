"""Health check endpoint provider for production observability."""

import time
from typing import Callable, Any


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
