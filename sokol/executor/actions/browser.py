"""
Browser action - Open URLs in browser
"""

from __future__ import annotations

import webbrowser

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class BrowserAction(BaseAction):
    """Action for browser operations."""
    
    async def execute(self, intent: Intent) -> ActionResult:
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
        url = intent.target or intent.params.get("url")
        
        if not url:
            return ActionResult(
                success=False,
                action="open_url",
                message="No URL provided",
            )
        
        # Ensure URL has protocol
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        
        try:
            webbrowser.open(url)
            return ActionResult(
                success=True,
                action="open_url",
                message=f"Opened: {url}",
                data={"url": url},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="open_url",
                message=f"Could not open URL: {url}",
                error=str(e),
            )
