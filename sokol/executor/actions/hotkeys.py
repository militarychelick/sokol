"""
Hotkey action
"""

from __future__ import annotations

import pyautogui

from .base import BaseAction
from ...core.intent import Intent
from ...core.result import ActionResult


class HotkeyAction(BaseAction):
    """Action for hotkey operations."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute hotkey action."""
        if intent.action_type == "press_hotkey":
            return self._press_hotkey(intent)
        else:
            return ActionResult(
                success=False,
                action=intent.action_type,
                message=f"Unknown hotkey action: {intent.action_type}",
            )
    
    def _press_hotkey(self, intent: Intent) -> ActionResult:
        """Press hotkey combination."""
        keys = intent.params.get("keys", [])
        
        if not keys:
            return ActionResult(
                success=False,
                action="press_hotkey",
                message="No keys specified",
            )
        
        try:
            pyautogui.hotkey(*keys)
            return ActionResult(
                success=True,
                action="press_hotkey",
                message=f"Pressed: {'+'.join(keys)}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="press_hotkey",
                message=f"Failed to press keys",
                error=str(e),
            )
