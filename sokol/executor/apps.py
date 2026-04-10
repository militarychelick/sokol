"""
Application launcher - Start and manage applications
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from ..core.agent import Step
from ..core.constants import ActionCategory
from ..core.exceptions import ExecutionError
from .base import BaseExecutor, ExecutionResult


class AppLauncher(BaseExecutor):
    """
    Launches applications on Windows.
    
    Supports:
    - Start Menu applications
    - Executable paths
    - Common shortcuts
    """
    
    # Common application names to executable mappings
    APP_MAPPINGS: dict[str, str] = {
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "spotify": "spotify.exe",
        "discord": "Discord.exe",
        "telegram": "telegram.exe",
        "steam": "steam.exe",
        "vlc": "vlc.exe",
        "code": "code.exe",
        "vscode": "code.exe",
    }
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute application launch step."""
        action = step.action
        params = step.params
        
        if action == "launch":
            return self._launch_app(params)
        elif action == "close":
            return self._close_app(params)
        elif action == "switch":
            return self._switch_app(params)
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown action: {action}",
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category in (
            ActionCategory.APP_LAUNCH,
            ActionCategory.APP_CLOSE,
            ActionCategory.APP_SWITCH,
        )
    
    def _launch_app(self, params: dict) -> ExecutionResult:
        """Launch an application."""
        app_name = params.get("app")
        path = params.get("path")
        
        if path:
            return self._launch_from_path(path)
        elif app_name:
            return self._launch_by_name(app_name)
        else:
            return ExecutionResult(
                success=False,
                message="No app name or path provided",
            )
    
    def _launch_from_path(self, path: str) -> ExecutionResult:
        """Launch application from path."""
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ExecutionResult(
                    success=False,
                    message=f"Path not found: {path}",
                )
            
            # Launch application
            subprocess.Popen([str(path_obj)], shell=True)
            
            return ExecutionResult(
                success=True,
                message=f"Launched: {path}",
                data={"path": path},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not launch: {path}",
                error=str(e),
            )
    
    def _launch_by_name(self, app_name: str) -> ExecutionResult:
        """Launch application by name."""
        app_name_lower = app_name.lower()
        
        # Check mappings
        if app_name_lower in self.APP_MAPPINGS:
            exe_name = self.APP_MAPPINGS[app_name_lower]
            return self._launch_from_path(exe_name)
        
        # Try Windows Search (win+r style)
        if self._launch_via_windows_search(app_name):
            return ExecutionResult(
                success=True,
                message=f"Launched: {app_name}",
                data={"app": app_name},
            )
        
        # Try to find in PATH
        if self._is_in_path(app_name):
            subprocess.Popen([app_name], shell=True)
            return ExecutionResult(
                success=True,
                message=f"Launched: {app_name}",
                data={"app": app_name},
            )
        
        # Try Start Menu
        if self._launch_from_start_menu(app_name):
            return ExecutionResult(
                success=True,
                message=f"Launched: {app_name}",
                data={"app": app_name},
            )
        
        return ExecutionResult(
            success=False,
            message=f"Could not find application: {app_name}",
        )
    
    def _launch_via_windows_search(self, app_name: str) -> bool:
        """Launch via Windows Search (Win+R style)."""
        try:
            # Use Windows Search via PowerShell
            ps_script = f'''
            Start-Process -FilePath "shell:AppsFolder" -ArgumentList "{app_name}"
            '''
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False
    
    def _is_in_path(self, app_name: str) -> bool:
        """Check if application is in system PATH."""
        try:
            subprocess.run(
                ["where", app_name],
                capture_output=True,
                check=True,
                timeout=2,
            )
            return True
        except Exception:
            return False
    
    def _launch_from_start_menu(self, app_name: str) -> bool:
        """Try to launch from Windows Start Menu."""
        try:
            start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            
            if not start_menu.exists():
                return False
            
            # Search for shortcuts
            for shortcut in start_menu.rglob("*.lnk"):
                if app_name.lower() in shortcut.name.lower():
                    # Launch shortcut
                    os.startfile(str(shortcut))
                    return True
            
            return False
        except Exception:
            return False
    
    def _close_app(self, params: dict) -> ExecutionResult:
        """Close an application."""
        app_name = params.get("app")
        
        if not app_name:
            return ExecutionResult(
                success=False,
                message="No app name provided",
            )
        
        try:
            # Try to find and close by window title
            import pywinauto
            from pywinauto.application import Application
            
            app = Application(backend="uia").connect(title_re=f".*{app_name}.*", timeout=2)
            window = app.top_window()
            window.close()
            
            return ExecutionResult(
                success=True,
                message=f"Closed: {app_name}",
            )
        except Exception as e:
            # Try taskkill
            try:
                subprocess.run(
                    ["taskkill", "/f", "/im", f"{app_name}.exe"],
                    capture_output=True,
                    timeout=5,
                )
                return ExecutionResult(
                    success=True,
                    message=f"Closed: {app_name}",
                )
            except Exception:
                return ExecutionResult(
                    success=False,
                    message=f"Could not close: {app_name}",
                    error=str(e),
                )
    
    def _switch_app(self, params: dict) -> ExecutionResult:
        """Switch to an application."""
        app_name = params.get("app")
        
        if not app_name:
            return ExecutionResult(
                success=False,
                message="No app name provided",
            )
        
        try:
            import pywinauto
            from pywinauto.application import Application
            
            app = Application(backend="uia").connect(title_re=f".*{app_name}.*", timeout=2)
            window = app.top_window()
            window.set_focus()
            
            return ExecutionResult(
                success=True,
                message=f"Switched to: {app_name}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not switch to: {app_name}",
                error=str(e),
            )
