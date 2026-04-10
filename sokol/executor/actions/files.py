"""
File action
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import BaseAction
from ...core.intent import Intent
from ...core.result import ActionResult


class FileAction(BaseAction):
    """Action for file operations."""
    
    def execute(self, intent: Intent) -> ActionResult:
        """Execute file action."""
        if intent.action_type == "search_file":
            return self._search(intent)
        elif intent.action_type == "open_file":
            return self._open(intent)
        else:
            return ActionResult(
                success=False,
                action=intent.action_type,
                message=f"Unknown file action: {intent.action_type}",
            )
    
    def _search(self, intent: Intent) -> ActionResult:
        """Search for files."""
        query = intent.params.get("query", intent.target)
        
        if not query:
            return ActionResult(
                success=False,
                action="search_file",
                message="No query specified",
            )
        
        try:
            # Simple search in home directory
            home = Path.home()
            results = []
            for root, dirs, files in os.walk(home):
                for file in files:
                    if query.lower() in file.lower():
                        results.append(os.path.join(root, file))
                        if len(results) >= 10:
                            break
                if len(results) >= 10:
                    break
            
            return ActionResult(
                success=True,
                action="search_file",
                message=f"Found {len(results)} results for '{query}'",
                data={"results": results},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="search_file",
                message=f"Search failed",
                error=str(e),
            )
    
    def _open(self, intent: Intent) -> ActionResult:
        """Open file."""
        return ActionResult(
            success=False,
            action="open_file",
            message="Open file not implemented yet",
        )
