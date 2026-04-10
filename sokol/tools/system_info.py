"""
System info tool - Get system information
"""

from typing import Any

import platform


class SystemInfoTool:
    """Tool for getting system information."""
    
    def get_info(self) -> dict[str, Any]:
        """Get basic system information."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
    
    def get_hostname(self) -> dict[str, Any]:
        """Get computer hostname."""
        return {
            "hostname": platform.node(),
        }
