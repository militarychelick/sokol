"""
Window action - Window management
"""

from __future__ import annotations

import pyautogui

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class WindowAction(BaseAction):
    """Action for window management."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute window action."""
        action = intent.params.get("window_action", intent.target)
        
        if action == "minimize":
            return self._minimize(intent)
        elif action == "maximize":
            return self._maximize(intent)
        elif action == "close":
            return self._close(intent)
        else:
            return ActionResult(
                success=False,
                action="manage_window",
                message=f"Unknown window action: {action}",
            )
    
    def _minimize(self, intent: Intent) -> ActionResult:
        """Minimize window."""
        try:
            pyautogui.hotkey("win", "down")
            return ActionResult(
                success=True,
                action="manage_window",
                message="Window minimized",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="manage_window",
                message="Could not minimize window",
                error=str(e),
            )
    
    def _maximize(self, intent: Intent) -> ActionResult:
        """Maximize window."""
        try:
            pyautogui.hotkey("win", "up")
            return ActionResult(
                success=True,
                action="manage_window",
                message="Window maximized",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="manage_window",
                message="Could not maximize window",
                error=str(e),
            )
    
    def _close(self, intent: Intent) -> ActionResult:
        """Close window."""
        try:
            pyautogui.hotkey("alt", "f4")
            return ActionResult(
                success=True,
                action="manage_window",
                message="Window closed",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="manage_window",
                message="Could not close window",
                error=str(e),
            )
