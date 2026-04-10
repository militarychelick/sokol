"""
Action dispatcher - Routes actions to appropriate action modules
"""

from __future__ import annotations

from typing import Any

from ..core.agent import ActionResult, Intent
from .actions.app_launcher import AppLauncherAction
from .actions.browser import BrowserAction
from .actions.hotkeys import HotkeyAction
from .actions.files import FileAction
from .actions.windows import WindowAction
from .actions.system import SystemAction


class ActionDispatcher:
    """
    Dispatches actions to appropriate action modules.
    
    This is THE single dispatcher - no other routing logic allowed.
    """
    
    # Action type to module mapping
    ACTION_MAP = {
        "launch_app": AppLauncherAction,
        "close_app": AppLauncherAction,
        "switch_app": AppLauncherAction,
        "open_url": BrowserAction,
        "press_hotkey": HotkeyAction,
        "search_file": FileAction,
        "manage_window": WindowAction,
        "system_action": SystemAction,
    }
    
    def __init__(self) -> None:
        # Initialize action modules
        self._actions: dict[str, Any] = {}
        for action_type, action_class in self.ACTION_MAP.items():
            self._actions[action_type] = action_class()
    
    async def dispatch(self, intent: Intent) -> ActionResult:
        """
        Dispatch intent to appropriate action module.
        
        Args:
            intent: Parsed intent with action_type, target, params
        
        Returns:
            ActionResult from action execution
        """
        action_type = intent.action_type
        
        if action_type not in self._actions:
            return ActionResult(
                success=False,
                action=action_type,
                message=f"Unknown action type: {action_type}",
            )
        
        action_module = self._actions[action_type]
        
        try:
            result = await action_module.execute(intent)
            return result
        except Exception as e:
            return ActionResult(
                success=False,
                action=action_type,
                message=f"Execution failed: {str(e)}",
                error=str(e),
            )
    
    async def execute_step(self, step: Any) -> ActionResult:
        """Execute a single step (for planned tasks)."""
        # Convert step to intent and dispatch
        intent = Intent(
            action_type=step.action,
            target=step.params.get("target"),
            params=step.params,
        )
        return await self.dispatch(intent)
