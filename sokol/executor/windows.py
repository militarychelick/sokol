"""
Windows automation using UIA (primary) and pyautogui (fallback)
"""

from __future__ import annotations

import time
from typing import Any

import pyautogui
import pywinauto
from pywinauto.application import Application

from ..core.agent import ActionResult, Step
from ..core.constants import ActionCategory
from ..core.exceptions import ExecutionError
from .base import BaseExecutor, ExecutionResult


class WindowsExecutor(BaseExecutor):
    """
    Executes Windows automation tasks using UIA.
    
    Primary: UIA (pywinauto) for accessibility-based automation
    Fallback: pyautogui for coordinate-based actions
    """
    
    def __init__(self) -> None:
        super().__init__()
        pyautogui.PAUSE = 0.1  # Small delay between actions
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute a Windows automation step."""
        action = step.action
        params = step.params
        
        try:
            if action == "window_activate":
                return self._activate_window(params)
            elif action == "window_minimize":
                return self._minimize_window(params)
            elif action == "window_maximize":
                return self._maximize_window(params)
            elif action == "window_close":
                return self._close_window(params)
            elif action == "click":
                return self._click_element(params)
            elif action == "type_text":
                return self._type_text(params)
            elif action == "press_key":
                return self._press_key(params)
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Unknown action: {action}",
                )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Execution failed: {action}",
                error=str(e),
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category == ActionCategory.WINDOW_MANAGE
    
    def _activate_window(self, params: dict) -> ExecutionResult:
        """Activate a window by title or handle."""
        title = params.get("title")
        
        if not title:
            return ExecutionResult(
                success=False,
                message="No window title provided",
            )
        
        try:
            # Find window by title
            app = Application(backend="uia").connect(title_re=f".*{title}.*", timeout=5)
            window = app.top_window()
            window.set_focus()
            
            return ExecutionResult(
                success=True,
                message=f"Activated window: {title}",
                data={"title": title},
            )
        except Exception as e:
            # Fallback: try pyautogui
            try:
                # List windows and try to activate
                return ExecutionResult(
                    success=False,
                    message=f"Could not activate window: {title}",
                    error=str(e),
                )
            except Exception:
                return ExecutionResult(
                    success=False,
                    message=f"Window not found: {title}",
                    error=str(e),
                )
    
    def _minimize_window(self, params: dict) -> ExecutionResult:
        """Minimize a window."""
        title = params.get("title")
        
        if not title:
            return ExecutionResult(
                success=False,
                message="No window title provided",
            )
        
        try:
            app = Application(backend="uia").connect(title_re=f".*{title}.*", timeout=5)
            window = app.top_window()
            window.minimize()
            
            return ExecutionResult(
                success=True,
                message=f"Minimized window: {title}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not minimize window: {title}",
                error=str(e),
            )
    
    def _maximize_window(self, params: dict) -> ExecutionResult:
        """Maximize a window."""
        title = params.get("title")
        
        if not title:
            return ExecutionResult(
                success=False,
                message="No window title provided",
            )
        
        try:
            app = Application(backend="uia").connect(title_re=f".*{title}.*", timeout=5)
            window = app.top_window()
            window.maximize()
            
            return ExecutionResult(
                success=True,
                message=f"Maximized window: {title}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not maximize window: {title}",
                error=str(e),
            )
    
    def _close_window(self, params: dict) -> ExecutionResult:
        """Close a window."""
        title = params.get("title")
        
        if not title:
            return ExecutionResult(
                success=False,
                message="No window title provided",
            )
        
        try:
            app = Application(backend="uia").connect(title_re=f".*{title}.*", timeout=5)
            window = app.top_window()
            window.close()
            
            return ExecutionResult(
                success=True,
                message=f"Closed window: {title}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not close window: {title}",
                error=str(e),
            )
    
    def _click_element(self, params: dict) -> ExecutionResult:
        """Click on UI element (UIA)."""
        # This would require more specific element identification
        # For now, use coordinate-based fallback
        x = params.get("x")
        y = params.get("y")
        
        if x is not None and y is not None:
            return self._click_coordinates(x, y)
        
        return ExecutionResult(
            success=False,
            message="Click requires coordinates or element identifier",
        )
    
    def _click_coordinates(self, x: int, y: int) -> ExecutionResult:
        """Click at coordinates (fallback)."""
        try:
            pyautogui.click(x, y)
            return ExecutionResult(
                success=True,
                message=f"Clicked at ({x}, {y})",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not click at ({x}, {y})",
                error=str(e),
            )
    
    def _type_text(self, params: dict) -> ExecutionResult:
        """Type text into focused window."""
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
                message=f"Typed text",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="Could not type text",
                error=str(e),
            )
    
    def _press_key(self, params: dict) -> ExecutionResult:
        """Press a keyboard key or combination."""
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
