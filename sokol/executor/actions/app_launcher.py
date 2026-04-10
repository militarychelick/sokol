"""
App launcher action - Launch/close applications
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class AppLauncherAction(BaseAction):
    """Action for launching/closing applications."""
    
    async def execute(self, intent: Intent) -> ActionResult:
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
        target = intent.target or intent.params.get("app")
        
        if not target:
            return ActionResult(
                success=False,
                action="launch_app",
                message="No app name provided",
            )
        
        try:
            # Try Windows Search first
            if self._launch_via_windows_search(target):
                return ActionResult(
                    success=True,
                    action="launch_app",
                    message=f"Launched: {target}",
                    data={"app": target},
                )
            
            # Try direct launch
            subprocess.Popen([target], shell=True)
            return ActionResult(
                success=True,
                action="launch_app",
                message=f"Launched: {target}",
                data={"app": target},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="launch_app",
                message=f"Could not launch: {target}",
                error=str(e),
            )
    
    def _launch_via_windows_search(self, app_name: str) -> bool:
        """Launch via Windows Search."""
        try:
            ps_script = f'Start-Process -FilePath "shell:AppsFolder" -ArgumentList "{app_name}"'
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False
    
    def _close(self, intent: Intent) -> ActionResult:
        """Close application."""
        target = intent.target or intent.params.get("app")
        
        if not target:
            return ActionResult(
                success=False,
                action="close_app",
                message="No app name provided",
            )
        
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", f"{target}.exe"],
                capture_output=True,
                timeout=5,
            )
            return ActionResult(
                success=True,
                action="close_app",
                message=f"Closed: {target}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="close_app",
                message=f"Could not close: {target}",
                error=str(e),
            )
    
    def _switch(self, intent: Intent) -> ActionResult:
        """Switch to application."""
        target = intent.target or intent.params.get("app")
        
        if not target:
            return ActionResult(
                success=False,
                action="switch_app",
                message="No app name provided",
            )
        
        # For now, just launch (Windows will switch if already open)
        return self._launch(intent)
