"""System info tool - read-only system queries."""

import platform
from typing import Any

from sokol.core.types import RiskLevel
from sokol.observability.logging import get_logger
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.system_info")


class SystemInfo(Tool[dict[str, Any]]):
    """Get system information - read only."""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return "Get system information: OS, CPU, memory, disk, processes"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ  # Always read-only

    @property
    def examples(self) -> list[str]:
        return [
            "what's my system info",
            "show memory usage",
            "list running processes",
            "check disk space",
        ]

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "enum": ["basic", "cpu", "memory", "disk", "processes", "network"],
                    "description": "Type of system information to retrieve",
                },
            },
            "required": ["info_type"],
        }

    def execute(self, info_type: str) -> ToolResult[dict[str, Any]]:
        """Get system information."""
        try:
            if info_type == "basic":
                return self._get_basic_info()
            elif info_type == "cpu":
                return self._get_cpu_info()
            elif info_type == "memory":
                return self._get_memory_info()
            elif info_type == "disk":
                return self._get_disk_info()
            elif info_type == "processes":
                return self._get_process_info()
            elif info_type == "network":
                return self._get_network_info()
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown info type: {info_type}",
                    risk_level=self.risk_level,
                )

        except Exception as e:
            logger.error_data("Failed to get system info", {"error": str(e)})
            return ToolResult(
                success=False,
                error=str(e),
                risk_level=self.risk_level,
            )

    def _get_basic_info(self) -> ToolResult[dict[str, Any]]:
        """Get basic system info."""
        return ToolResult(
            success=True,
            data={
                "system": platform.system(),
                "node": platform.node(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            risk_level=self.risk_level,
        )

    def _get_cpu_info(self) -> ToolResult[dict[str, Any]]:
        """Get CPU info."""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            return ToolResult(
                success=True,
                data={
                    "cpu_percent": cpu_percent,
                    "cpu_count": cpu_count,
                    "cpu_freq_current": cpu_freq.current if cpu_freq else None,
                    "cpu_freq_min": cpu_freq.min if cpu_freq else None,
                    "cpu_freq_max": cpu_freq.max if cpu_freq else None,
                },
                risk_level=self.risk_level,
            )
        except ImportError:
            return ToolResult(
                success=True,
                data={
                    "cpu_count": platform.processor(),
                    "note": "psutil not available for detailed CPU info",
                },
                risk_level=self.risk_level,
            )

    def _get_memory_info(self) -> ToolResult[dict[str, Any]]:
        """Get memory info."""
        try:
            import psutil

            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return ToolResult(
                success=True,
                data={
                    "total_gb": round(mem.total / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "percent": mem.percent,
                    "swap_total_gb": round(swap.total / (1024**3), 2),
                    "swap_used_gb": round(swap.used / (1024**3), 2),
                    "swap_percent": swap.percent,
                },
                risk_level=self.risk_level,
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="psutil required for memory info",
                risk_level=self.risk_level,
            )

    def _get_disk_info(self) -> ToolResult[dict[str, Any]]:
        """Get disk info."""
        try:
            import psutil

            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    pass

            return ToolResult(
                success=True,
                data={"partitions": partitions},
                risk_level=self.risk_level,
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="psutil required for disk info",
                risk_level=self.risk_level,
            )

    def _get_process_info(self) -> ToolResult[dict[str, Any]]:
        """Get process info."""
        try:
            import psutil

            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    processes.append({
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "cpu_percent": proc.info["cpu_percent"],
                        "memory_percent": proc.info["memory_percent"],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Sort by CPU usage
            processes.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
            top_processes = processes[:20]

            return ToolResult(
                success=True,
                data={
                    "total_count": len(processes),
                    "top_processes": top_processes,
                },
                risk_level=self.risk_level,
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="psutil required for process info",
                risk_level=self.risk_level,
            )

    def _get_network_info(self) -> ToolResult[dict[str, Any]]:
        """Get network info."""
        try:
            import psutil

            # Get network interfaces
            interfaces = []
            net_if_addrs = psutil.net_if_addrs()
            for name, addrs in net_if_addrs.items():
                interface = {"name": name, "addresses": []}
                for addr in addrs:
                    interface["addresses"].append({
                        "family": str(addr.family),
                        "address": addr.address,
                    })
                interfaces.append(interface)

            # Get network IO stats
            net_io = psutil.net_io_counters()

            return ToolResult(
                success=True,
                data={
                    "interfaces": interfaces,
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                },
                risk_level=self.risk_level,
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="psutil required for network info",
                risk_level=self.risk_level,
            )
