"""App launcher tool - safely open applications."""

import os
import subprocess
from typing import Any

from sokol.core.types import RiskLevel
from sokol.observability.debug import dry_run_mode
from sokol.observability.logging import get_logger
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.app_launcher")

# Common Windows apps with their executable names
COMMON_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "browser": "msedge.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "task manager": "taskmgr.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
}


class AppLauncher(Tool[dict[str, Any]]):
    """Launch applications on Windows."""

    @property
    def name(self) -> str:
        return "app_launcher"

    @property
    def description(self) -> str:
        return "Launch Windows applications by name or path"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ  # Opening apps is generally safe

    @property
    def examples(self) -> list[str]:
        return [
            "open notepad",
            "launch calculator",
            "start chrome",
            "open vscode",
        ]

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name or path of the application to launch",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command line arguments",
                },
                "elevated": {
                    "type": "boolean",
                    "description": "Run as administrator",
                    "default": False,
                },
            },
            "required": ["app_name"],
        }

    def execute(
        self,
        app_name: str,
        args: list[str] | None = None,
        elevated: bool = False,
    ) -> ToolResult[dict[str, Any]]:
        """Execute app launch."""
        # Normalize app name
        app_name_lower = app_name.lower().strip()

        # Check common apps first
        executable = COMMON_APPS.get(app_name_lower, app_name)

        # Build command
        cmd = [executable]
        if args:
            cmd.extend(args)

        logger.info_data(
            "Launching application",
            {"app": app_name, "executable": executable, "args": args, "elevated": elevated},
        )

        # Dry run mode
        if dry_run_mode():
            logger.info("DRY RUN: Would launch app")
            return ToolResult(
                success=True,
                data={
                    "app_name": app_name,
                    "executable": executable,
                    "dry_run": True,
                },
                risk_level=self.risk_level,
            )

        try:
            if elevated:
                # Run as admin using ShellExecute
                import ctypes

                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    executable,
                    " ".join(args) if args else None,
                    None,
                    1,  # SW_SHOWNORMAL
                )
                process_info = {"pid": None, "elevated": True}
            else:
                # Normal launch
                process = subprocess.Popen(
                    cmd,
                    shell=False,
                    start_new_session=True,
                )
                process_info = {"pid": process.pid, "elevated": False}

            return ToolResult(
                success=True,
                data={
                    "app_name": app_name,
                    "executable": executable,
                    "process": process_info,
                },
                risk_level=self.risk_level,
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"Application not found: {app_name}",
                risk_level=self.risk_level,
            )
        except Exception as e:
            logger.error_data("Failed to launch app", {"error": str(e)})
            return ToolResult(
                success=False,
                error=f"Failed to launch {app_name}: {str(e)}",
                risk_level=self.risk_level,
            )
