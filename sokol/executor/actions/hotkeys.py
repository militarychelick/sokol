"""
Hotkey action - Press keyboard shortcuts
"""

from __future__ import annotations

import pyautogui

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class HotkeyAction(BaseAction):
    """Action for hotkey operations."""
    
    async def execute(self, intent: Intent) -> ActionResult:
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
        keys = intent.target or intent.params.get("keys")
        
        if not keys:
            return ActionResult(
                success=False,
                action="press_hotkey",
                message="No keys provided",
            )
        
        # Handle both string and list formats
        if isinstance(keys, str):
            keys = keys.split("+")
        elif isinstance(keys, list):
            pass  # Already a list
        else:
            keys = [str(keys)]
        
        try:
            pyautogui.hotkey(*keys)
            return ActionResult(
                success=True,
                action="press_hotkey",
                message=f"Pressed: {'+'.join(keys)}",
                data={"keys": keys},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="press_hotkey",
                message=f"Could not press keys",
                error=str(e),
            )
