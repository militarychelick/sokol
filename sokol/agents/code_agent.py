# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Code Agent for Script Generation and Execution"""
import asyncio
import logging
import tempfile
import subprocess
import sys
import os
from typing import Any, Dict, List, Optional

from ..core import CodeExecutor, INTERRUPT
from ..policy import check_system_action
from .base import AgentBase, AgentResponse, AgentStatus, AgentCapability

logger = logging.getLogger(__name__)


class CodeAgent(AgentBase):
    """
    Code Agent - Writes and executes primitive Python/Bash scripts for automation
    Handles file sorting, text processing, and simple automation tasks
    """
    
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="generate_script",
                description="Generate Python/Bash scripts for automation",
                max_execution_time=20
            ),
            AgentCapability(
                name="execute_code",
                description="Execute Python code in isolated environment",
                requires_system=True,
                max_execution_time=45
            ),
            AgentCapability(
                name="file_automation",
                description="Automate file operations (sort, rename, organize)",
                requires_system=True,
                max_execution_time=30
            ),
            AgentCapability(
                name="text_processing",
                description="Process and manipulate text data",
                max_execution_time=15
            )
        ]
        
        super().__init__("code_agent", capabilities)
        
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """Process code agent request"""
        self._start_execution()
        
        try:
            action = request.get("action", "").lower()
            
            if action == "generate_script":
                return await self._generate_script(request)
            elif action == "execute_code":
                return await self._execute_code(request)
            elif action == "file_automation":
                return await self._file_automation(request)
            elif action == "text_processing":
                return await self._text_processing(request)
            elif action == "automate":
                return await self._handle_automation_request(request)
            else:
                return await self._handle_code_request(request)
                
        except Exception as e:
            self.logger.error(f"Code operation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _generate_script(self, request: Dict[str, Any]) -> AgentResponse:
        """Generate automation script"""
        task_description = request.get("task", "")
        script_type = request.get("script_type", "python")
        
        if not task_description:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No task description provided"
            )
        
        try:
            # Generate script based on task
            if script_type.lower() == "python":
                script_code = self._generate_python_script(task_description)
            elif script_type.lower() == "bash":
                script_code = self._generate_bash_script(task_description)
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unsupported script type: {script_type}"
                )
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Generated {script_type} script",
                data={
                    "script_code": script_code,
                    "script_type": script_type,
                    "task": task_description
                },
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Script generation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _execute_code(self, request: Dict[str, Any]) -> AgentResponse:
        """Execute Python code"""
        code = request.get("code", "")
        
        if not code:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No code provided"
            )
        
        try:
            # Check safety policy
            if not check_system_action("execute_code", {"code": code}):
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Code execution blocked by safety policy"
                )
            
            # Execute code using existing CodeExecutor
            success, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None, CodeExecutor.execute, code
            )
            
            status = AgentStatus.SUCCESS if success else AgentStatus.FAILED
            
            return self._create_response(
                status=status,
                content=f"Code execution {'completed' if success else 'failed'}",
                data={
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": success
                },
                confidence=0.9 if success else 0.3
            )
            
        except Exception as e:
            self.logger.error(f"Code execution failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _file_automation(self, request: Dict[str, Any]) -> AgentResponse:
        """Automate file operations"""
        operation = request.get("operation", "").lower()
        file_path = request.get("file_path", "")
        pattern = request.get("pattern", "")
        
        try:
            # Check safety policy for file operations
            if not check_system_action("file_automation", {"operation": operation, "path": file_path}):
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="File automation blocked by safety policy"
                )
            
            if operation == "sort":
                result = await self._sort_files(file_path, pattern)
            elif operation == "rename":
                result = await self._rename_files(file_path, pattern)
            elif operation == "organize":
                result = await self._organize_files(file_path, pattern)
            elif operation == "cleanup":
                result = await self._cleanup_files(file_path, pattern)
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unknown file operation: {operation}"
                )
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"File {operation} completed",
                data=result,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"File automation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _text_processing(self, request: Dict[str, Any]) -> AgentResponse:
        """Process and manipulate text data"""
        operation = request.get("operation", "").lower()
        text = request.get("text", "")
        pattern = request.get("pattern", "")
        
        try:
            if operation == "extract":
                result = self._extract_text_pattern(text, pattern)
            elif operation == "replace":
                replacement = request.get("replacement", "")
                result = self._replace_text_pattern(text, pattern, replacement)
            elif operation == "count":
                result = self._count_text_pattern(text, pattern)
            elif operation == "format":
                format_type = request.get("format_type", "json")
                result = self._format_text(text, format_type)
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unknown text operation: {operation}"
                )
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Text {operation} completed",
                data=result,
                confidence=0.9
            )
            
        except Exception as e:
            self.logger.error(f"Text processing failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _handle_automation_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Handle general automation requests"""
        task = request.get("task", str(request))
        
        # Try to understand the automation task
        task_lower = task.lower()
        
        if "sort" in task_lower and "file" in task_lower:
            # Extract file path and pattern
            file_path = self._extract_file_path(task)
            return await self._file_automation({"operation": "sort", "file_path": file_path})
        
        elif "rename" in task_lower and "file" in task_lower:
            file_path = self._extract_file_path(task)
            return await self._file_automation({"operation": "rename", "file_path": file_path})
        
        elif "organize" in task_lower or "cleanup" in task_lower:
            file_path = self._extract_file_path(task)
            operation = "organize" if "organize" in task_lower else "cleanup"
            return await self._file_automation({"operation": operation, "file_path": file_path})
        
        else:
            # Generate script for custom automation
            return await self._generate_script({"task": task, "script_type": "python"})
    
    async def _handle_code_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Handle general code requests"""
        text = request.get("text", str(request))
        
        # Check if it contains code
        if CodeExecutor.has_code(text):
            return await self._execute_code({"code": text})
        else:
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Code agent ready. Available operations: generate_script, execute_code, file_automation, text_processing",
                data={"available_operations": self.list_capabilities()},
                confidence=0.7
            )
    
    def _generate_python_script(self, task: str) -> str:
        """Generate Python script for automation task"""
        task_lower = task.lower()
        
        if "sort" in task_lower and "file" in task_lower:
            return '''import os
import glob
from pathlib import Path

def sort_files(directory, pattern="*"):
    """Sort files in directory by name/size/date"""
    path = Path(directory)
    if not path.exists():
        print(f"Directory {directory} does not exist")
        return
    
    files = list(path.glob(pattern))
    files.sort(key=lambda f: f.stat().st_mtime)  # Sort by modification time
    
    print(f"Found {len(files)} files:")
    for file in files:
        print(f"  {file.name} - {file.stat().st_size} bytes")

if __name__ == "__main__":
    sort_files(".", "*.txt")  # Modify as needed
'''
        
        elif "rename" in task_lower:
            return '''import os
import re
from pathlib import Path

def rename_files(directory, pattern, replacement):
    """Rename files matching pattern"""
    path = Path(directory)
    count = 0
    
    for file in path.glob(pattern):
        new_name = re.sub(pattern, replacement, file.name)
        new_path = file.with_name(new_name)
        
        if not new_path.exists():
            file.rename(new_path)
            print(f"Renamed: {file.name} -> {new_name}")
            count += 1
        else:
            print(f"Skipped: {new_name} already exists")
    
    print(f"Renamed {count} files")

if __name__ == "__main__":
    rename_files(".", r"(.*)", r"new_\\1")  # Modify as needed
'''
        
        else:
            # Generic automation script
            return f'''import os
import sys
from pathlib import Path

def automate_task():
    """Automation task: {task}"""
    print("Starting automation task...")
    
    # TODO: Implement your automation logic here
    # Example:
    # - List files in directory
    # - Process files
    # - Generate output
    
    print("Task completed")

if __name__ == "__main__":
    automate_task()
'''
    
    def _generate_bash_script(self, task: str) -> str:
        """Generate Bash script for automation task"""
        task_lower = task.lower()
        
        if "sort" in task_lower and "file" in task_lower:
            return '''#!/bin/bash
# Sort files by modification time
echo "Sorting files..."
ls -lt *.txt 2>/dev/null || echo "No .txt files found"
echo "Done."
'''
        
        elif "cleanup" in task_lower:
            return '''#!/bin/bash
# Cleanup temporary files
echo "Cleaning up..."
rm -f *.tmp *.log 2>/dev/null
echo "Cleanup completed."
'''
        
        else:
            return f'''#!/bin/bash
# Automation task: {task}
echo "Starting automation..."
# TODO: Add your commands here
echo "Task completed."
'''
    
    async def _sort_files(self, file_path: str, pattern: str) -> Dict[str, Any]:
        """Sort files in directory"""
        import os
        import glob
        from pathlib import Path
        
        path = Path(file_path) if file_path else Path(".")
        pattern = pattern or "*"
        
        if not path.exists():
            return {"error": f"Directory {file_path} does not exist"}
        
        files = list(path.glob(pattern))
        files.sort(key=lambda f: f.stat().st_mtime)
        
        sorted_files = [
            {
                "name": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime
            }
            for f in files
        ]
        
        return {"sorted_files": sorted_files, "count": len(sorted_files)}
    
    async def _rename_files(self, file_path: str, pattern: str) -> Dict[str, Any]:
        """Rename files matching pattern"""
        import re
        from pathlib import Path
        
        path = Path(file_path) if file_path else Path(".")
        renamed_count = 0
        
        for file in path.glob("*"):
            if file.is_file():
                new_name = re.sub(pattern, f"renamed_{file.name}", file.name)
                new_path = file.with_name(new_name)
                
                if not new_path.exists():
                    file.rename(new_path)
                    renamed_count += 1
        
        return {"renamed_count": renamed_count}
    
    async def _organize_files(self, file_path: str, pattern: str) -> Dict[str, Any]:
        """Organize files into subdirectories"""
        import os
        import shutil
        from pathlib import Path
        
        path = Path(file_path) if file_path else Path(".")
        organized_count = 0
        
        # Create subdirectories by file extension
        for file in path.glob("*"):
            if file.is_file():
                ext = file.suffix.lower()
                if ext:
                    subdir = path / ext[1:]  # Remove dot
                    subdir.mkdir(exist_ok=True)
                    
                    new_path = subdir / file.name
                    if not new_path.exists():
                        shutil.move(str(file), str(new_path))
                        organized_count += 1
        
        return {"organized_count": organized_count}
    
    async def _cleanup_files(self, file_path: str, pattern: str) -> Dict[str, Any]:
        """Cleanup temporary files"""
        import os
        from pathlib import Path
        
        path = Path(file_path) if file_path else Path(".")
        pattern = pattern or "*.tmp"
        
        cleaned_count = 0
        for file in path.glob(pattern):
            if file.is_file():
                file.unlink()
                cleaned_count += 1
        
        return {"cleaned_count": cleaned_count}
    
    def _extract_text_pattern(self, text: str, pattern: str) -> Dict[str, Any]:
        """Extract text matching pattern"""
        import re
        matches = re.findall(pattern, text)
        return {"matches": matches, "count": len(matches)}
    
    def _replace_text_pattern(self, text: str, pattern: str, replacement: str) -> Dict[str, Any]:
        """Replace text matching pattern"""
        import re
        result = re.sub(pattern, replacement, text)
        return {"result": result, "replacements": len(re.findall(pattern, text))}
    
    def _count_text_pattern(self, text: str, pattern: str) -> Dict[str, Any]:
        """Count occurrences of pattern in text"""
        import re
        count = len(re.findall(pattern, text))
        return {"count": count}
    
    def _format_text(self, text: str, format_type: str) -> Dict[str, Any]:
        """Format text in different formats"""
        if format_type.lower() == "json":
            import json
            try:
                result = json.dumps({"text": text}, indent=2, ensure_ascii=False)
            except:
                result = text
        elif format_type.lower() == "uppercase":
            result = text.upper()
        elif format_type.lower() == "lowercase":
            result = text.lower()
        else:
            result = text
        
        return {"result": result, "format": format_type}
    
    def _extract_file_path(self, text: str) -> str:
        """Extract file path from text"""
        import re
        # Look for file paths in the text
        path_pattern = r'[A-Za-z]:\\[^"\'\s]+|/[^"\'\s]+'
        matches = re.findall(path_pattern, text)
        return matches[0] if matches else "."
