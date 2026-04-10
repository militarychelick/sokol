"""
Tests for executor basic actions
"""

import pytest

from sokol.executor.apps import AppLauncher
from sokol.executor.browser import BrowserExecutor
from sokol.executor.files import FileExecutor
from sokol.executor.hotkeys import HotkeyExecutor
from sokol.core.agent import Step
from sokol.core.constants import ActionCategory


def test_app_launcher_can_execute():
    """Test app launcher executor capability."""
    executor = AppLauncher()
    
    assert executor.can_execute(ActionCategory.APP_LAUNCH)
    assert executor.can_execute(ActionCategory.APP_CLOSE)
    assert not executor.can_execute(ActionCategory.FILE_SEARCH)


def test_browser_executor_can_execute():
    """Test browser executor capability."""
    executor = BrowserExecutor()
    
    assert executor.can_execute(ActionCategory.BROWSER_OPEN)
    assert executor.can_execute(ActionCategory.BROWSER_NAVIGATE)
    assert not executor.can_execute(ActionCategory.APP_LAUNCH)


def test_file_executor_can_execute():
    """Test file executor capability."""
    executor = FileExecutor()
    
    assert executor.can_execute(ActionCategory.FILE_OPEN)
    assert executor.can_execute(ActionCategory.FILE_SEARCH)
    assert not executor.can_execute(ActionCategory.APP_LAUNCH)


def test_hotkey_executor_can_execute():
    """Test hotkey executor capability."""
    executor = HotkeyExecutor()
    
    assert executor.can_execute(ActionCategory.HOTKEY)
    assert not executor.can_execute(ActionCategory.APP_LAUNCH)


def test_app_launcher_launch_no_params():
    """Test app launcher with no parameters."""
    executor = AppLauncher()
    step = Step(action="launch", action_category=ActionCategory.APP_LAUNCH, params={})
    
    result = executor.execute(step)
    assert not result.success
    assert "No app name" in result.message
