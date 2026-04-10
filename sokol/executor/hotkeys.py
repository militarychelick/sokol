"""
Hotkey simulation - Press keyboard shortcuts
"""

from __future__ import annotations

from typing import Any

import pyautogui

from ..core.agent import Step
from ..core.constants import ActionCategory
from .base import BaseExecutor, ExecutionResult


class HotkeyExecutor(BaseExecutor):
    """
    Simulates keyboard shortcuts and hotkeys.
    
    Supports:
    - Single keys
    - Key combinations (Ctrl+C, Alt+Tab, etc.)
    - Special keys (Enter, Escape, etc.)
    """
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute hotkey step."""
        action = step.action
        params = step.params
        
        if action == "press":
            return self._press_key(params)
        elif action == "hotkey":
            return self._press_hotkey(params)
        elif action == "type":
            return self._type_text(params)
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown action: {action}",
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category == ActionCategory.HOTKEY
    
    def _press_key(self, params: dict) -> ExecutionResult:
        """Press a single key."""
        key = params.get("key")
        
        if not key:
            return ExecutionResult(
                success=False,
                message="No key provided",
            )
        
        try:
            pyautogui.press(key)
            return ExecutionResult(
                success=True,
                message=f"Pressed key: {key}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not press key: {key}",
                error=str(e),
            )
    
    def _press_hotkey(self, params: dict) -> ExecutionResult:
        """Press a key combination (hotkey)."""
        keys = params.get("keys")
        
        if not keys:
            return ExecutionResult(
                success=False,
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
            return ExecutionResult(
                success=True,
                message=f"Pressed hotkey: {'+'.join(keys)}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not press hotkey",
                error=str(e),
            )
    
    def _type_text(self, params: dict) -> ExecutionResult:
        """Type text."""
        text = params.get("text")
        
        if not text:
            return ExecutionResult(
                success=False,
                message="No text provided",
            )
        
        try:
            pyautogui.write(text)
            return ExecutionResult(
                success=True,
                message="Typed text",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not type text",
                error=str(e),
            )
