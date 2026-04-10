"""
App launcher action
"""

from __future__ import annotations

import subprocess

from .base import BaseAction
from ...core.intent import Intent
from ...core.result import ActionResult


class AppLauncherAction(BaseAction):
    """Action for launching/closing applications."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute app launch/close action."""
        if intent.action_type == "launch_app":
            return self._launch(intent)
        elif intent.action_type == "close_app":
            return self._close(intent)
        elif intent.action_type == "switch_app":
            return self._switch(intent)
        else:
            return ActionResult(
                success=False,
                action=intent.action_type,
                message=f"Unknown app action: {intent.action_type}",
            )
    
    def _launch(self, intent: Intent) -> ActionResult:
        """Launch application."""
        app = intent.params.get("app", intent.target)
        
        try:
            subprocess.Popen(app)
            return ActionResult(
                success=True,
                action="launch_app",
                message=f"Launched: {app}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="launch_app",
                message=f"Failed to launch {app}",
                error=str(e),
            )
    
    def _close(self, intent: Intent) -> ActionResult:
        """Close application."""
        app = intent.params.get("app", intent.target)
        
        try:
            subprocess.Popen(["taskkill", "/F", "/IM", f"{app}.exe"])
            return ActionResult(
                success=True,
                action="close_app",
                message=f"Closed: {app}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="close_app",
                message=f"Failed to close {app}",
                error=str(e),
            )
    
    def _switch(self, intent: Intent) -> ActionResult:
        """Switch to application."""
        return ActionResult(
            success=False,
            action="switch_app",
            message="Switch not implemented yet",
        )
