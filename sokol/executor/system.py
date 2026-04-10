"""
System actions - Limited system operations
"""

from __future__ import annotations

import subprocess
from typing import Any

from ..core.agent import Step
from ..core.constants import ActionCategory
from .base import BaseExecutor, ExecutionResult


class SystemExecutor(BaseExecutor):
    """
    Executes limited system actions.
    
    All system actions require policy approval.
    """
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute system step."""
        action = step.action
        params = step.params
        
        if action == "shutdown":
            return self._shutdown(params)
        elif action == "restart":
            return self._restart(params)
        elif action == "sleep":
            return self._sleep(params)
        elif action == "lock":
            return self._lock(params)
        elif action == "volume":
            return self._set_volume(params)
        elif action == "brightness":
            return self._set_brightness(params)
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown action: {action}",
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category in (
            ActionCategory.SYSTEM_POWER,
            ActionCategory.SYSTEM_SETTINGS,
        )
    
    def _shutdown(self, params: dict) -> ExecutionResult:
        """Shutdown the computer."""
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", "10"],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message="Shutting down in 10 seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not shutdown",
                error=str(e),
            )
    
    def _restart(self, params: dict) -> ExecutionResult:
        """Restart the computer."""
        try:
            subprocess.run(
                ["shutdown", "/r", "/t", "10"],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message="Restarting in 10 seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not restart",
                error=str(e),
            )
    
    def _sleep(self, params: dict) -> ExecutionResult:
        """Put computer to sleep."""
        try:
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message="Going to sleep",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not sleep",
                error=str(e),
            )
    
    def _lock(self, params: dict) -> ExecutionResult:
        """Lock the screen."""
        try:
            subprocess.run(
                ["rundll32.exe", "user32.dll,LockWorkStation"],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message="Screen locked",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not lock screen",
                error=str(e),
            )
    
    def _set_volume(self, params: dict) -> ExecutionResult:
        """Set system volume."""
        volume = params.get("volume")  # 0-100
        
        if volume is None:
            return ExecutionResult(
                success=False,
                message="No volume level provided",
            )
        
        try:
            # Use PowerShell to set volume
            ps_script = f"""
            $obj = New-Object -ComObject WScript.Shell
            $obj.SendKeys("vol:{volume}%")
            """
            subprocess.run(
                ["powershell", "-Command", ps_script],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message=f"Volume set to {volume}%",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not set volume",
                error=str(e),
            )
    
    def _set_brightness(self, params: dict) -> ExecutionResult:
        """Set screen brightness."""
        brightness = params.get("brightness")  # 0-100
        
        if brightness is None:
            return ExecutionResult(
                success=False,
                message="No brightness level provided",
            )
        
        try:
            # Use PowerShell to set brightness
            ps_script = f"""
            $brightness = {brightness}
            $monitor = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods
            $monitor.WmiSetBrightness(1, $brightness)
            """
            subprocess.run(
                ["powershell", "-Command", ps_script],
                check=True,
                timeout=5,
            )
            return ExecutionResult(
                success=True,
                message=f"Brightness set to {brightness}%",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not set brightness",
                error=str(e),
            )
