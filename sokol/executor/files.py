"""
File operations - Safe file operations only
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.agent import Step
from ..core.constants import ActionCategory
from ..core.exceptions import RestrictedActionError
from .base import BaseExecutor, ExecutionResult


class FileExecutor(BaseExecutor):
    """
    Executes safe file operations.
    
    Supported operations (safe):
    - Open files
    - Search files
    - Copy files
    - List directories
    
    Dangerous operations (require policy approval):
    - Delete files (handled by policy layer)
    - Modify files (handled by policy layer)
    """
    
    def execute(self, step: Step) -> ExecutionResult:
        """Execute file operation step."""
        action = step.action
        params = step.params
        
        if action == "open":
            return self._open_file(params)
        elif action == "search":
            return self._search_files(params)
        elif action == "copy":
            return self._copy_file(params)
        elif action == "list":
            return self._list_directory(params)
        elif action == "get_info":
            return self._get_file_info(params)
        else:
            return ExecutionResult(
                success=False,
                message=f"Unknown action: {action}",
            )
    
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if executor can handle action."""
        return action_category in (
            ActionCategory.FILE_OPEN,
            ActionCategory.FILE_SEARCH,
            ActionCategory.FILE_COPY,
        )
    
    def _open_file(self, params: dict) -> ExecutionResult:
        """Open a file with default application."""
        path = params.get("path")
        
        if not path:
            return ExecutionResult(
                success=False,
                message="No file path provided",
            )
        
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ExecutionResult(
                    success=False,
                    message=f"File not found: {path}",
                )
            
            # Open with default application
            os.startfile(str(path_obj))
            
            return ExecutionResult(
                success=True,
                message=f"Opened: {path}",
                data={"path": path},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not open file: {path}",
                error=str(e),
            )
    
    def _search_files(self, params: dict) -> ExecutionResult:
        """Search for files by name or pattern."""
        query = params.get("query")
        search_dir = params.get("directory", os.path.expanduser("~"))
        
        if not query:
            return ExecutionResult(
                success=False,
                message="No search query provided",
            )
        
        try:
            search_path = Path(search_dir)
            if not search_path.exists():
                return ExecutionResult(
                    success=False,
                    message=f"Search directory not found: {search_dir}",
                )
            
            results = []
            query_lower = query.lower()
            
            # Search recursively
            for item in search_path.rglob("*"):
                if query_lower in item.name.lower():
                    results.append(str(item))
            
            return ExecutionResult(
                success=True,
                message=f"Found {len(results)} results for '{query}'",
                data={"results": results[:20], "total": len(results)},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Search failed: {query}",
                error=str(e),
            )
    
    def _copy_file(self, params: dict) -> ExecutionResult:
        """Copy a file."""
        source = params.get("source")
        destination = params.get("destination")
        
        if not source or not destination:
            return ExecutionResult(
                success=False,
                message="Source or destination not provided",
            )
        
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                return ExecutionResult(
                    success=False,
                    message=f"Source not found: {source}",
                )
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            import shutil
            shutil.copy2(source_path, dest_path)
            
            return ExecutionResult(
                success=True,
                message=f"Copied {source} to {destination}",
                data={"source": source, "destination": destination},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not copy file",
                error=str(e),
            )
    
    def _list_directory(self, params: dict) -> ExecutionResult:
        """List contents of a directory."""
        path = params.get("path", os.path.expanduser("~"))
        
        try:
            dir_path = Path(path)
            
            if not dir_path.exists():
                return ExecutionResult(
                    success=False,
                    message=f"Directory not found: {path}",
                )
            
            if not dir_path.is_dir():
                return ExecutionResult(
                    success=False,
                    message=f"Not a directory: {path}",
                )
            
            items = []
            for item in dir_path.iterdir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                })
            
            return ExecutionResult(
                success=True,
                message=f"Listed {len(items)} items",
                data={"items": items},
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not list directory",
                error=str(e),
            )
    
    def _get_file_info(self, params: dict) -> ExecutionResult:
        """Get information about a file."""
        path = params.get("path")
        
        if not path:
            return ExecutionResult(
                success=False,
                message="No file path provided",
            )
        
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ExecutionResult(
                    success=False,
                    message=f"File not found: {path}",
                )
            
            stat = path_obj.stat()
            
            return ExecutionResult(
                success=True,
                message=f"File info: {path}",
                data={
                    "path": path,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "is_dir": path_obj.is_dir(),
                    "is_file": path_obj.is_file(),
                },
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Could not get file info",
                error=str(e),
            )
