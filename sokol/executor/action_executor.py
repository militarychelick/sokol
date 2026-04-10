"""
Action executor - Main orchestrator for all executors
"""

from __future__ import annotations

from typing import Any

from ..core.agent import ActionResult, Intent, Step
from ..core.config import Config
from ..core.constants import ActionCategory
from ..core.exceptions import ExecutionError
from .apps import AppLauncher
from .base import BaseExecutor, ExecutionResult
from .browser import BrowserExecutor
from .files import FileExecutor
from .hotkeys import HotkeyExecutor
from .system import SystemExecutor
from .windows import WindowsExecutor


class ActionExecutor:
    """
    Main executor that routes actions to appropriate sub-executors.
    
    This is THE single execution point for all actions.
    No other execution paths allowed.
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
        
        # Initialize all specialized executors
        self._executors: dict[ActionCategory, BaseExecutor] = {
            ActionCategory.APP_LAUNCH: AppLauncher(),
            ActionCategory.APP_CLOSE: AppLauncher(),
            ActionCategory.APP_SWITCH: AppLauncher(),
            ActionCategory.WINDOW_MANAGE: WindowsExecutor(),
            ActionCategory.BROWSER_OPEN: BrowserExecutor(),
            ActionCategory.BROWSER_NAVIGATE: BrowserExecutor(),
            ActionCategory.FILE_OPEN: FileExecutor(),
            ActionCategory.FILE_SEARCH: FileExecutor(),
            ActionCategory.FILE_COPY: FileExecutor(),
            ActionCategory.HOTKEY: HotkeyExecutor(),
            ActionCategory.SYSTEM_POWER: SystemExecutor(),
            ActionCategory.SYSTEM_SETTINGS: SystemExecutor(),
        }
    
    async def execute(self, intent: Intent) -> ActionResult:
        """
        Execute an intent.
        
        Args:
            intent: Parsed user intent
        
        Returns:
            ActionResult with execution results
        """
        if intent.action_category is None:
            return ActionResult(
                success=False,
                action="unknown",
                message="No action category specified",
            )
        
        # Get appropriate executor
        executor = self._get_executor(intent.action_category)
        
        if executor is None:
            return ActionResult(
                success=False,
                action=intent.action_category.value,
                message=f"No executor for action: {intent.action_category}",
            )
        
        # Build step from intent
        step = self._intent_to_step(intent)
        
        # Execute with retry logic
        result = await self._execute_with_retry(executor, step)
        
        # Convert to ActionResult
        return ActionResult(
            success=result.success,
            action=intent.action_category.value,
            message=result.message,
            data=result.data,
            error=result.error,
        )
    
    async def _execute_with_retry(self, executor: Any, step: Step, max_retries: int = 2) -> ExecutionResult:
        """Execute step with retry logic."""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                # Run synchronous executor in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, executor.execute, step)
                
                if result.success:
                    return result
                
                # If failed and not last attempt, wait and retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                return result
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                return ExecutionResult(
                    success=False,
                    message=f"Execution failed after {max_retries} attempts",
                    error=str(e),
                )
    
    async def execute_step(self, step: Step) -> ActionResult:
        """
        Execute a single step (for planned tasks).
        
        Args:
            step: Step to execute
        
        Returns:
            ActionResult with execution results
        """
        executor = self._get_executor(step.action_category)
        
        if executor is None:
            return ActionResult(
                success=False,
                action=step.action,
                message=f"No executor for action: {step.action_category}",
            )
        
        result = executor.execute(step)
        
        return ActionResult(
            success=result.success,
            action=step.action,
            message=result.message,
            data=result.data,
            error=result.error,
        )
    
    def _get_executor(self, category: ActionCategory) -> BaseExecutor | None:
        """Get executor for action category."""
        # Direct match
        if category in self._executors:
            return self._executors[category]
        
        # Fallback mapping
        fallback_map = {
            ActionCategory.BROWSER_TAB: self._executors.get(ActionCategory.BROWSER_OPEN),
            ActionCategory.FILE_MODIFY: self._executors.get(ActionCategory.FILE_OPEN),
            ActionCategory.FILE_MOVE: self._executors.get(ActionCategory.FILE_COPY),
        }
        
        return fallback_map.get(category)
    
    def _intent_to_step(self, intent: Intent) -> Step:
        """Convert intent to execution step."""
        action = self._map_intent_to_action(intent)
        params = intent.entities.copy()
        
        return Step(
            action=action,
            action_category=intent.action_category or ActionCategory.UNKNOWN,
            params=params,
        )
    
    def _map_intent_to_action(self, intent: Intent) -> str:
        """Map intent type and category to specific action."""
        category = intent.action_category
        
        if category == ActionCategory.APP_LAUNCH:
            return "launch"
        elif category == ActionCategory.APP_CLOSE:
            return "close"
        elif category == ActionCategory.APP_SWITCH:
            return "switch"
        elif category == ActionCategory.WINDOW_MANAGE:
            return self._map_window_action(intent)
        elif category == ActionCategory.BROWSER_OPEN:
            return "open_browser"
        elif category == ActionCategory.BROWSER_NAVIGATE:
            return "open_url"
        elif category == ActionCategory.FILE_OPEN:
            return "open"
        elif category == ActionCategory.FILE_SEARCH:
            return "search"
        elif category == ActionCategory.FILE_COPY:
            return "copy"
        elif category == ActionCategory.HOTKEY:
            return "hotkey"
        elif category == ActionCategory.SYSTEM_POWER:
            return self._map_power_action(intent)
        elif category == ActionCategory.SYSTEM_SETTINGS:
            return self._map_settings_action(intent)
        else:
            return "unknown"
    
    def _map_window_action(self, intent: Intent) -> str:
        """Map window management intent to specific action."""
        text = intent.raw_text.lower()
        
        if "minimize" in text:
            return "window_minimize"
        elif "maximize" in text:
            return "window_maximize"
        elif "close" in text:
            return "window_close"
        else:
            return "window_activate"
    
    def _map_power_action(self, intent: Intent) -> str:
        """Map power action intent to specific action."""
        text = intent.raw_text.lower()
        
        if "shutdown" in text:
            return "shutdown"
        elif "restart" in text or "reboot" in text:
            return "restart"
        elif "sleep" in text:
            return "sleep"
        else:
            return "lock"
    
    def _map_settings_action(self, intent: Intent) -> str:
        """Map settings intent to specific action."""
        text = intent.raw_text.lower()
        
        if "volume" in text:
            return "volume"
        elif "brightness" in text:
            return "brightness"
        else:
            return "unknown"
