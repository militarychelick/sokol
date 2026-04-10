"""
System action - System operations
"""

from __future__ import annotations

import subprocess

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class SystemAction(BaseAction):
    """Action for system operations."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute system action."""
        action = intent.params.get("system_action", intent.target)
        
        if action == "shutdown":
            return self._shutdown(intent)
        elif action == "restart":
            return self._restart(intent)
        elif action == "sleep":
            return self._sleep(intent)
        else:
            return ActionResult(
                success=False,
                action="system_action",
                message=f"Unknown system action: {action}",
            )
    
    def _shutdown(self, intent: Intent) -> ActionResult:
        """Shutdown system."""
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", "10"],
                check=True,
                timeout=5,
            )
            return ActionResult(
                success=True,
                action="system_action",
                message="Shutting down in 10 seconds",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="system_action",
                message="Could not shutdown",
                error=str(e),
            )
    
    def _restart(self, intent: Intent) -> ActionResult:
        """Restart system."""
        try:
            subprocess.run(
                ["shutdown", "/r", "/t", "10"],
                check=True,
                timeout=5,
            )
            return ActionResult(
                success=True,
                action="system_action",
                message="Restarting in 10 seconds",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="system_action",
                message="Could not restart",
                error=str(e),
            )
    
    def _sleep(self, intent: Intent) -> ActionResult:
        """Put system to sleep."""
        try:
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                check=True,
                timeout=5,
            )
            return ActionResult(
                success=True,
                action="system_action",
                message="Going to sleep",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="system_action",
                message="Could not sleep",
                error=str(e),
            )
