"""
Action dispatcher - Routes actions to appropriate action modules
"""

from __future__ import annotations

from typing import Any

from ..core.intent import Intent
from ..core.result import ActionResult


class ActionDispatcher:
    """
    Dispatcher - routing only, no business logic.
    
    action_type → action module → execute()
    """
    
    ACTION_MAP = {
        "launch_app": "app_launcher",
        "close_app": "app_launcher",
        "switch_app": "app_launcher",
        "open_url": "browser",
        "press_hotkey": "hotkeys",
        "search_file": "files",
        "open_file": "files",
        "manage_window": "windows",
        "system_action": "system",
    }
    
    def __init__(self) -> None:
        self._actions: dict[str, Any] = {}
    
    def dispatch(self, intent: Intent) -> ActionResult:
        """Dispatch intent to appropriate action module (synchronous)."""
        action_type = intent.action_type
        
        if action_type not in self.ACTION_MAP:
            return ActionResult(
                success=False,
                action=action_type,
                message=f"Unknown action type: {action_type}",
            )
        
        module_name = self.ACTION_MAP[action_type]
        action_module = self._get_action_module(module_name)
        
        try:
            result = action_module.execute(intent)
            return result
        except Exception as e:
            return ActionResult(
                success=False,
                action=action_type,
                message=f"Execution failed: {str(e)}",
                error=str(e),
            )
    
    def _get_action_module(self, module_name: str) -> Any:
        """Get or create action module."""
        if module_name not in self._actions:
            if module_name == "app_launcher":
                from .actions.app_launcher import AppLauncherAction
                self._actions[module_name] = AppLauncherAction()
            elif module_name == "browser":
                from .actions.browser import BrowserAction
                self._actions[module_name] = BrowserAction()
            elif module_name == "hotkeys":
                from .actions.hotkeys import HotkeyAction
                self._actions[module_name] = HotkeyAction()
            elif module_name == "files":
                from .actions.files import FileAction
                self._actions[module_name] = FileAction()
            elif module_name == "windows":
                from .actions.windows import WindowAction
                self._actions[module_name] = WindowAction()
            elif module_name == "system":
                from .actions.system import SystemAction
                self._actions[module_name] = SystemAction()
        
        return self._actions[module_name]
    
    async def dispatch_async(self, intent: Intent) -> ActionResult:
        """Async wrapper for dispatch (for agent compatibility)."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.dispatch, intent)
