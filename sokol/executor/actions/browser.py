"""
Browser action
"""

from __future__ import annotations

import webbrowser

from .base import BaseAction
from ...core.intent import Intent
from ...core.result import ActionResult


class BrowserAction(BaseAction):
    """Action for browser operations."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute browser action."""
        if intent.action_type == "open_url":
            return self._open_url(intent)
        else:
            return ActionResult(
                success=False,
                action=intent.action_type,
                message=f"Unknown browser action: {intent.action_type}",
            )
    
    def _open_url(self, intent: Intent) -> ActionResult:
        """Open URL in browser."""
        url = intent.params.get("url", intent.target)
        
        if not url:
            return ActionResult(
                success=False,
                action="open_url",
                message="No URL specified",
            )
        
        try:
            webbrowser.open(url)
            return ActionResult(
                success=True,
                action="open_url",
                message=f"Opened: {url}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="open_url",
                message=f"Failed to open {url}",
                error=str(e),
            )
