"""
Browser control - Open URLs, manage tabs
"""

from __future__ import annotations

import subprocess
from typing import Any

from ..core.agent import Step
from ..core.constants import ActionCategory
from .base import BaseExecutor, ExecutionResult


class BrowserExecutor(BaseExecutor):
    """
    Controls web browsers.
    
    Supports:
    - Opening URLs in default browser
    - Opening specific browsers
    """
    
    # Browser executables
    BROWSER_PATHS: dict[str, str] = {
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
    }
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute browser step."""
        action = step.action
        params = step.params
        
        if action == "open_url":
            return self._open_url(params)
        elif action == "open_browser":
            return self._open_browser(params)
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown action: {action}",
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category in (
            ActionCategory.BROWSER_OPEN,
            ActionCategory.BROWSER_NAVIGATE,
        )
    
    def _open_url(self, params: dict) -> ExecutionResult:
        """Open URL in browser."""
        url = params.get("url")
        browser = params.get("browser")
        
        if not url:
            return ExecutionResult(
                success=False,
                message="No URL provided",
            )
        
        # Ensure URL has protocol
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        
        try:
            if browser:
                return self._open_in_specific_browser(url, browser)
            else:
                return self._open_in_default_browser(url)
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not open URL: {url}",
                error=str(e),
            )
    
    def _open_in_default_browser(self, url: str) -> ExecutionResult:
        """Open URL in default browser."""
        try:
            import webbrowser
            webbrowser.open(url)
            return ExecutionResult(
                success=True,
                message=f"Opened URL: {url}",
                data={"url": url},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not open default browser",
                error=str(e),
            )
    
    def _open_in_specific_browser(self, url: str, browser: str) -> ExecutionResult:
        """Open URL in specific browser."""
        browser_lower = browser.lower()
        
        if browser_lower in self.BROWSER_PATHS:
            exe = self.BROWSER_PATHS[browser_lower]
            subprocess.Popen([exe, url], shell=True)
            
            return ExecutionResult(
                success=True,
                message=f"Opened {url} in {browser}",
                data={"url": url, "browser": browser},
            )
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown browser: {browser}",
            )
    
    def _open_browser(self, params: dict) -> ExecutionResult:
        """Open browser without URL."""
        browser = params.get("browser", "chrome")
        
        if browser in self.BROWSER_PATHS:
            exe = self.BROWSER_PATHS[browser]
            subprocess.Popen([exe], shell=True)
            
            return ExecutionResult(
                success=True,
                message=f"Opened {browser}",
            )
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown browser: {browser}",
            )
