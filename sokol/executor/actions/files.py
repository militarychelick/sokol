"""
File action - File operations
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import BaseAction
from ...core.agent import ActionResult, Intent


class FileAction(BaseAction):
    """Action for file operations."""
    
    async def execute(self, intent: Intent) -> ActionResult:
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
        query = intent.target or intent.params.get("query")
        search_dir = intent.params.get("directory", os.path.expanduser("~"))
        
        if not query:
            return ActionResult(
                success=False,
                action="search_file",
                message="No search query provided",
            )
        
        try:
            search_path = Path(search_dir)
            if not search_path.exists():
                return ActionResult(
                    success=False,
                    action="search_file",
                    message=f"Directory not found: {search_dir}",
                )
            
            results = []
            query_lower = query.lower()
            
            # Search recursively
            for item in search_path.rglob("*"):
                if query_lower in item.name.lower():
                    results.append(str(item))
            
            return ActionResult(
                success=True,
                action="search_file",
                message=f"Found {len(results)} results for '{query}'",
                data={"results": results[:20], "total": len(results)},
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
        path = intent.target or intent.params.get("path")
        
        if not path:
            return ActionResult(
                success=False,
                action="open_file",
                message="No file path provided",
            )
        
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return ActionResult(
                    success=False,
                    action="open_file",
                    message=f"File not found: {path}",
                )
            
            os.startfile(str(path_obj))
            return ActionResult(
                success=True,
                action="open_file",
                message=f"Opened: {path}",
                data={"path": path},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action="open_file",
                message=f"Could not open file",
                error=str(e),
            )
