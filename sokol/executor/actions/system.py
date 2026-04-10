"""
System action
"""

from __future__ import annotations

import subprocess

from .base import BaseAction
from ...core.intent import Intent
from ...core.result import ActionResult


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
        return ActionResult(
            success=False,
            action="system_action",
            message="Shutdown not implemented (safety restriction)",
        )
    
    def _restart(self, intent: Intent) -> ActionResult:
        """Restart system."""
        return ActionResult(
            success=False,
            action="system_action",
            message="Restart not implemented (safety restriction)",
        )
    
    def _sleep(self, intent: Intent) -> ActionResult:
        """Sleep system."""
        return ActionResult(
            success=False,
            action="system_action",
            message="Sleep not implemented (safety restriction)",
        )
