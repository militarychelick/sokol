# -*- coding: utf-8 -*-
"""SOKOL v8.0 - System Agent for Windows Control"""
import asyncio
import os
import subprocess
import logging
from typing import Any, Dict, List, Optional

from ..config import RUS_APP_MAP, SYSTEM_TOOLS, FOLDER_ALIASES
from ..automation import GUIAutomation
from ..policy import check_system_action
from .base import AgentBase, AgentResponse, AgentStatus, AgentCapability

logger = logging.getLogger(__name__)


class SystemAgent(AgentBase):
    """
    System Agent - Main executor for Windows operations
    Works with os, subprocess, pywinauto for app launching, window management, and process control
    """
    
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="launch_app",
                description="Launch applications and programs",
                requires_system=True,
                max_execution_time=10
            ),
            AgentCapability(
                name="manage_windows",
                description="Manage window operations (minimize, maximize, close)",
                requires_system=True,
                max_execution_time=5
            ),
            AgentCapability(
                name="process_control",
                description="Control processes (start, stop, monitor)",
                requires_system=True,
                max_execution_time=8
            ),
            AgentCapability(
                name="file_operations",
                description="Basic file and folder operations",
                requires_system=True,
                max_execution_time=15
            ),
            AgentCapability(
                name="system_info",
                description="Get system information and status",
                max_execution_time=5
            )
        ]
        
        super().__init__("system_agent", capabilities)
        
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """Process system agent request"""
        self._start_execution()
        
        try:
            action = request.get("action", "").lower()
            
            if action == "launch_app":
                return await self._launch_application(request)
            elif action == "manage_windows":
                return await self._manage_windows(request)
            elif action == "process_control":
                return await self._control_process(request)
            elif action == "file_operations":
                return await self._file_operations(request)
            elif action == "system_info":
                return await self._get_system_info(request)
            elif action == "execute":
                return await self._execute_command(request)
            else:
                return await self._handle_general_request(request)
                
        except Exception as e:
            self.logger.error(f"System operation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _launch_application(self, request: Dict[str, Any]) -> AgentResponse:
        """Launch application"""
        app_name = request.get("app_name", "").lower()
        app_path = request.get("app_path", "")
        
        if not app_name and not app_path:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No application name or path provided"
            )
        
        try:
            # Check safety policy
            if not check_system_action("launch_app", {"app_name": app_name, "app_path": app_path}):
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Application launch blocked by safety policy"
                )
            
            # Resolve application name to path
            if app_path:
                launch_path = app_path
            else:
                launch_path = self._resolve_app_name(app_name)
            
            if not launch_path:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Could not resolve application: {app_name}"
                )
            
            # Launch application
            result = await asyncio.get_event_loop().run_in_executor(
                None, GUIAutomation.run_program, launch_path
            )
            
            if result["success"]:
                return self._create_response(
                    status=AgentStatus.SUCCESS,
                    content=f"Launched {app_name or app_path}",
                    data=result,
                    confidence=0.9
                )
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=result.get("error", "Launch failed")
                )
                
        except Exception as e:
            self.logger.error(f"App launch failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _manage_windows(self, request: Dict[str, Any]) -> AgentResponse:
        """Manage window operations"""
        operation = request.get("operation", "").lower()
        window_title = request.get("window_title", "")
        
        try:
            if operation == "minimize":
                success = await self._minimize_window(window_title)
            elif operation == "maximize":
                success = await self._maximize_window(window_title)
            elif operation == "close":
                success = await self._close_window(window_title)
            elif operation == "focus":
                success = await self._focus_window(window_title)
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unknown window operation: {operation}"
                )
            
            if success:
                return self._create_response(
                    status=AgentStatus.SUCCESS,
                    content=f"Window {operation} completed",
                    data={"operation": operation, "window": window_title},
                    confidence=0.8
                )
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Failed to {operation} window: {window_title}"
                )
                
        except Exception as e:
            self.logger.error(f"Window operation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _control_process(self, request: Dict[str, Any]) -> AgentResponse:
        """Control processes"""
        operation = request.get("operation", "").lower()
        process_name = request.get("process_name", "")
        
        try:
            # Check safety policy for dangerous operations
            if operation in ["kill", "stop"]:
                if not check_system_action("kill_process", {"process_name": process_name}):
                    return self._create_response(
                        status=AgentStatus.FAILED,
                        error_message="Process termination blocked by safety policy"
                    )
            
            if operation == "kill":
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: GUIAutomation.terminate_process(process_name)
                )
            elif operation == "list":
                result = await self._list_processes()
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unknown process operation: {operation}"
                )
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Process {operation} completed",
                data=result,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Process control failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _file_operations(self, request: Dict[str, Any]) -> AgentResponse:
        """Basic file operations"""
        operation = request.get("operation", "").lower()
        file_path = request.get("file_path", "")
        
        try:
            # Check safety policy for file operations
            if operation in ["delete", "move", "copy"]:
                if not check_system_action("file_operation", {"operation": operation, "path": file_path}):
                    return self._create_response(
                        status=AgentStatus.FAILED,
                        error_message=f"File {operation} blocked by safety policy"
                    )
            
            if operation == "exists":
                exists = os.path.exists(file_path)
                return self._create_response(
                    status=AgentStatus.SUCCESS,
                    content=f"File exists: {exists}",
                    data={"exists": exists, "path": file_path},
                    confidence=1.0
                )
            elif operation == "list":
                if os.path.isdir(file_path):
                    files = os.listdir(file_path)
                    return self._create_response(
                        status=AgentStatus.SUCCESS,
                        content=f"Listed {len(files)} items",
                        data={"files": files, "path": file_path},
                        confidence=0.9
                    )
                else:
                    return self._create_response(
                        status=AgentStatus.FAILED,
                        error_message=f"Path is not a directory: {file_path}"
                    )
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message=f"Unsupported file operation: {operation}"
                )
                
        except Exception as e:
            self.logger.error(f"File operation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _get_system_info(self, request: Dict[str, Any]) -> AgentResponse:
        """Get system information"""
        try:
            import psutil
            
            info = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": {
                    "C:": psutil.disk_usage('C:\\').percent if os.path.exists('C:\\') else None
                },
                "running_processes": len(psutil.pids())
            }
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="System information retrieved",
                data=info,
                confidence=0.9
            )
            
        except ImportError:
            # Fallback without psutil
            info = {
                "platform": os.name,
                "python_version": os.sys.version,
                "current_directory": os.getcwd()
            }
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Basic system information retrieved",
                data=info,
                confidence=0.7
            )
        except Exception as e:
            self.logger.error(f"System info failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _execute_command(self, request: Dict[str, Any]) -> AgentResponse:
        """Execute system command"""
        command = request.get("command", "")
        
        if not command:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No command provided"
            )
        
        try:
            # Check safety policy
            if not check_system_action("execute_command", {"command": command}):
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Command execution blocked by safety policy"
                )
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return self._create_response(
                status=AgentStatus.SUCCESS if result.returncode == 0 else AgentStatus.FAILED,
                content=f"Command executed with return code {result.returncode}",
                data={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                },
                confidence=0.8
            )
            
        except subprocess.TimeoutExpired:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="Command execution timed out"
            )
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _handle_general_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Handle general system requests"""
        text = request.get("text", str(request)).lower()
        
        # Try to interpret natural language requests
        if "launch" in text or "open" in text or "run" in text:
            # Extract app name
            app_name = self._extract_app_name(text)
            if app_name:
                return await self._launch_application({"app_name": app_name})
        
        elif "close" in text or "exit" in text:
            # Extract app name to close
            app_name = self._extract_app_name(text)
            if app_name:
                return await self._control_process({"operation": "kill", "process_name": app_name})
        
        elif "minimize" in text or "maximize" in text:
            return await self._manage_windows({"operation": text.split()[0], "window_title": ""})
        
        # Default: return info about available operations
        return self._create_response(
            status=AgentStatus.SUCCESS,
            content="System agent ready. Available operations: launch_app, manage_windows, process_control, file_operations, system_info",
            data={"available_operations": self.list_capabilities()},
            confidence=0.7
        )
    
    def _resolve_app_name(self, app_name: str) -> Optional[str]:
        """Resolve app name to executable path"""
        # Check Russian app mappings
        if app_name in RUS_APP_MAP:
            return RUS_APP_MAP[app_name]
        
        # Check system tools
        if app_name in SYSTEM_TOOLS:
            return SYSTEM_TOOLS[app_name]
        
        # Check folder aliases
        if app_name in FOLDER_ALIASES:
            return FOLDER_ALIASES[app_name]
        
        # Return as-is if it looks like a path
        if os.path.exists(app_name):
            return app_name
        
        # Try common executable names
        common_names = {
            "chrome": "chrome",
            "firefox": "firefox", 
            "telegram": "telegram",
            "discord": "discord",
            "steam": "steam"
        }
        
        return common_names.get(app_name.lower())
    
    def _extract_app_name(self, text: str) -> Optional[str]:
        """Extract app name from natural language text"""
        words = text.split()
        
        for word in words:
            if word.lower() in RUS_APP_MAP or word.lower() in SYSTEM_TOOLS:
                return word.lower()
        
        return None
    
    async def _minimize_window(self, title: str) -> bool:
        """Minimize window by title"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].minimize()
                return True
        except ImportError:
            pass
        return False
    
    async def _maximize_window(self, title: str) -> bool:
        """Maximize window by title"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].maximize()
                return True
        except ImportError:
            pass
        return False
    
    async def _close_window(self, title: str) -> bool:
        """Close window by title"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].close()
                return True
        except ImportError:
            pass
        return False
    
    async def _focus_window(self, title: str) -> bool:
        """Focus window by title"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                return True
        except ImportError:
            pass
        return False
    
    async def _list_processes(self) -> Dict[str, Any]:
        """List running processes"""
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.info['cpu_percent']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {"processes": processes[:50]}  # Limit to 50 processes
            
        except ImportError:
            # Fallback without psutil
            return {"processes": [], "note": "psutil not available"}
        except Exception as e:
            return {"processes": [], "error": str(e)}
