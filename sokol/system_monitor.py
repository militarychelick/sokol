# -*- coding: utf-8 -*-
"""
SOKOL System Monitor — Real-time CPU/RAM/GPU monitoring
v8.0: System resource monitoring with optional widget overlay
"""
import os
import sys
import time
import ctypes
import threading
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict, Any


class SystemMonitor:
    """
    Real-time system resource monitor.
    Tracks CPU, RAM, disk, and network usage.
    Can run standalone or as an overlay widget.
    """

    def __init__(self, refresh_interval=2.0):
        self.refresh_interval = refresh_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._data: Dict[str, Any] = {}
        self._data_lock = threading.Lock()
        self._callbacks = []
        self._has_psutil = self._check_psutil()

    def _check_psutil(self) -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _get_cpu_percent(self) -> Optional[float]:
        """Get CPU usage percentage."""
        if self._has_psutil:
            try:
                import psutil
                return psutil.cpu_percent(interval=0.5)
            except Exception:
                pass
        # Fallback to WMIC
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage", "/value"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000
            )
            for line in result.stdout.strip().splitlines():
                if "=" in line:
                    return float(line.split("=", 1)[1].strip())
        except Exception:
            pass
        return None

    def _get_ram_info(self) -> Optional[Dict[str, float]]:
        """Get RAM usage info: {used_mb, total_mb, percent}."""
        if self._has_psutil:
            try:
                import psutil
                mem = psutil.virtual_memory()
                return {
                    "used_mb": mem.used / (1024 ** 2),
                    "total_mb": mem.total / (1024 ** 2),
                    "percent": mem.percent,
                    "available_mb": mem.available / (1024 ** 2)
                }
            except Exception:
                pass
        # Fallback to WMIC
        try:
            result = subprocess.run(
                ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000
            )
            vals = {}
            for line in result.stdout.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip()] = float(v.strip())
            total_kb = vals.get("TotalVisibleMemorySize", 0)
            free_kb = vals.get("FreePhysicalMemory", 0)
            if total_kb:
                total_mb = total_kb / 1024
                used_mb = (total_kb - free_kb) / 1024
                return {
                    "used_mb": used_mb,
                    "total_mb": total_mb,
                    "percent": (used_mb / total_mb) * 100,
                    "available_mb": free_kb / 1024
                }
        except Exception:
            pass
        return None

    def _get_disk_info(self) -> Dict[str, Dict[str, float]]:
        """Get disk usage for C:, D:, E:, F: drives."""
        disks = {}
        for letter in "CDEF":
            try:
                import shutil
                usage = shutil.disk_usage(f"{letter}:\\")
                disks[letter] = {
                    "total_gb": usage.total / (1024 ** 3),
                    "free_gb": usage.free / (1024 ** 3),
                    "used_gb": (usage.total - usage.free) / (1024 ** 3),
                    "percent": ((usage.total - usage.free) / usage.total) * 100
                }
            except Exception:
                pass
        return disks

    def _get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """Get GPU info via WMIC if available."""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM", "/value"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000
            )
            gpus = []
            current = {}
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    current[k.strip()] = v.strip()
                    if len(current) >= 2:
                        gpus.append(current)
                        current = {}
            if gpus:
                return {"gpus": gpus, "count": len(gpus)}
        except Exception:
            pass
        return None

    def _get_network_info(self) -> Optional[Dict[str, Any]]:
        """Get network connection info."""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Get WiFi SSID if available
            ssid = None
            try:
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=0x08000000
                )
                for line in result.stdout.splitlines():
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
            
            return {"local_ip": local_ip, "ssid": ssid, "connected": True}
        except Exception:
            return {"connected": False}

    def _get_battery_info(self) -> Optional[Dict[str, Any]]:
        """Get battery status."""
        if self._has_psutil:
            try:
                import psutil
                battery = psutil.sensors_battery()
                if battery:
                    return {
                        "percent": battery.percent,
                        "charging": battery.power_plugged,
                        "secs_left": battery.secsleft if battery.secsleft > 0 else None
                    }
            except Exception:
                pass
        # Fallback to Windows API
        try:
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]
            status = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                if status.BatteryLifePercent != 255:
                    return {
                        "percent": status.BatteryLifePercent,
                        "charging": status.ACLineStatus == 1,
                        "secs_left": status.BatteryLifeTime if status.BatteryLifeTime != 0xFFFFFFFF else None
                    }
        except Exception:
            pass
        return None

    def _get_process_count(self) -> int:
        """Get count of running processes."""
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000
            )
            return len([line for line in result.stdout.splitlines() if line.strip()])
        except Exception:
            return 0

    def _update(self):
        """Update all metrics."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "cpu": self._get_cpu_percent(),
            "ram": self._get_ram_info(),
            "disks": self._get_disk_info(),
            "gpu": self._get_gpu_info(),
            "network": self._get_network_info(),
            "battery": self._get_battery_info(),
            "processes": self._get_process_count(),
        }
        with self._data_lock:
            self._data = data
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception:
                pass

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(self.refresh_interval)

    def start(self):
        """Start monitoring in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def get_data(self) -> Dict[str, Any]:
        """Get current monitoring data (thread-safe)."""
        with self._data_lock:
            return self._data.copy()

    def register_callback(self, callback):
        """Register callback to be called on each update."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """Unregister callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def format_report(self) -> str:
        """Format current data as readable report."""
        data = self.get_data()
        lines = ["━━━ SOKOL System Monitor ━━━"]
        lines.append(f"  🕐 {datetime.now().strftime('%H:%M:%S')}")
        lines.append("")
        
        # CPU
        cpu = data.get("cpu")
        if cpu is not None:
            bar = self._make_bar(cpu)
            lines.append(f"  🖥️  CPU:    {bar} {cpu:.0f}%")
        
        # RAM
        ram = data.get("ram")
        if ram:
            bar = self._make_bar(ram["percent"])
            used_gb = ram["used_mb"] / 1024
            total_gb = ram["total_mb"] / 1024
            lines.append(f"  💾 RAM:    {bar} {ram['percent']:.0f}% ({used_gb:.1f}/{total_gb:.1f} GB)")
        
        # Disks
        disks = data.get("disks", {})
        for letter, info in disks.items():
            bar = self._make_bar(info["percent"], width=10)
            lines.append(f"  💿 Disk {letter}: {bar} {info['percent']:.0f}% ({info['free_gb']:.1f} GB free)")
        
        # GPU
        gpu = data.get("gpu")
        if gpu and gpu.get("gpus"):
            for g in gpu["gpus"][:1]:  # Show first GPU
                name = g.get("Name", "Unknown GPU")[:30]
                lines.append(f"  🎮 GPU:    {name}")
        
        # Network
        net = data.get("network")
        if net:
            if net.get("connected"):
                ssid_str = f" (WiFi: {net['ssid']})" if net.get("ssid") else ""
                lines.append(f"  🌐 Net:    {net['local_ip']}{ssid_str}")
            else:
                lines.append(f"  🌐 Net:    ❌ Disconnected")
        
        # Battery
        battery = data.get("battery")
        if battery:
            icon = "🔌" if battery["charging"] else "🔋"
            lines.append(f"  {icon} Batt:   {battery['percent']:.0f}%{' (charging)' if battery['charging'] else ''}")
        
        # Processes
        procs = data.get("processes")
        if procs:
            lines.append(f"  ⚙️  Procs:  {procs} processes")
        
        lines.append("━" * 35)
        return "\n".join(lines)

    @staticmethod
    def _make_bar(percent: float, width: int = 15) -> str:
        """Create ASCII progress bar."""
        filled = int(width * min(percent, 100) / 100)
        return "█" * filled + "░" * (width - filled)

    def is_high_load(self, cpu_threshold: float = 90.0, ram_threshold: float = 90.0) -> Tuple[bool, str]:
        """Check if system is under high load."""
        data = self.get_data()
        cpu = data.get("cpu")
        ram = data.get("ram")
        
        if cpu is not None and cpu > cpu_threshold:
            return True, f"⚠️ High CPU usage: {cpu:.0f}%"
        if ram and ram["percent"] > ram_threshold:
            return True, f"⚠️ High RAM usage: {ram['percent']:.0f}%"
        return False, ""


class SystemMonitorWidget:
    """
    Optional Tkinter overlay widget for system monitoring.
    Shows small window in corner with live stats.
    """
    
    def __init__(self, monitor: SystemMonitor, corner="top-right"):
        self.monitor = monitor
        self.corner = corner
        self.root = None
        self.labels = {}
        self._running = False

    def _create_window(self):
        """Create the widget window."""
        import tkinter as tk
        
        self.root = tk.Toplevel()
        self.root.title("Sokol Monitor")
        self.root.configure(bg="#1a1b26")
        self.root.overrideredirect(True)  # No window decorations
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.9)  # Slight transparency
        
        # Set size
        self.root.geometry("200x120")
        
        # Position in corner
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        if self.corner == "top-right":
            x = screen_width - 220
            y = 20
        elif self.corner == "top-left":
            x = 20
            y = 20
        elif self.corner == "bottom-right":
            x = screen_width - 220
            y = screen_height - 140
        else:  # bottom-left
            x = 20
            y = screen_height - 140
        
        self.root.geometry(f"200x120+{x}+{y}")
        
        # Create labels
        font = ("Consolas", 10)
        colors = {"cpu": "#7aa2f7", "ram": "#9ece6a", "bg": "#1a1b26", "fg": "#c0caf5"}
        
        self.labels["cpu"] = tk.Label(self.root, text="CPU: --%", font=font, 
                                       bg=colors["bg"], fg=colors["cpu"])
        self.labels["cpu"].pack(anchor="w", padx=10, pady=2)
        
        self.labels["ram"] = tk.Label(self.root, text="RAM: --%", font=font,
                                       bg=colors["bg"], fg=colors["ram"])
        self.labels["ram"].pack(anchor="w", padx=10, pady=2)
        
        # Make draggable
        self.root.bind("<Button-1>", self._start_drag)
        self.root.bind("<B1-Motion>", self._on_drag)
        
        # Right-click to close
        self.root.bind("<Button-3>", lambda e: self.stop())

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _update_widget(self, data: Dict[str, Any]):
        """Update widget with new data."""
        if not self.root:
            return
        
        cpu = data.get("cpu")
        if cpu is not None:
            self.labels["cpu"].config(text=f"CPU: {cpu:.0f}%")
        
        ram = data.get("ram")
        if ram:
            self.labels["ram"].config(text=f"RAM: {ram['percent']:.0f}%")

    def start(self):
        """Start the widget."""
        import tkinter as tk
        
        if self._running:
            return
        self._running = True
        
        # Need a root window to create Toplevel
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()  # Hide root window
        
        self._create_window()
        self.monitor.register_callback(self._update_widget)
        self.monitor.start()
        
        # Start update loop
        self._schedule_update()
        self._tk_root.mainloop()

    def _schedule_update(self):
        """Schedule periodic updates."""
        if self._running and self._tk_root:
            self._tk_root.after(1000, self._schedule_update)

    def stop(self):
        """Stop the widget."""
        self._running = False
        self.monitor.unregister_callback(self._update_widget)
        self.monitor.stop()
        if self.root:
            self.root.destroy()
            self.root = None
        if hasattr(self, '_tk_root'):
            self._tk_root.quit()


# Global monitor instance (singleton)
_global_monitor: Optional[SystemMonitor] = None


def get_monitor(refresh_interval: float = 2.0) -> SystemMonitor:
    """Get or create global system monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor(refresh_interval)
    return _global_monitor


def format_quick_status() -> str:
    """Quick one-line system status."""
    monitor = get_monitor()
    data = monitor.get_data()
    parts = []
    
    cpu = data.get("cpu")
    if cpu is not None:
        parts.append(f"CPU {cpu:.0f}%")
    
    ram = data.get("ram")
    if ram:
        parts.append(f"RAM {ram['percent']:.0f}%")
    
    return " | ".join(parts) if parts else "System status unavailable"


if __name__ == "__main__":
    # Test mode: print system stats
    monitor = SystemMonitor(refresh_interval=1.0)
    monitor.start()
    
    try:
        while True:
            print("\033[H\033[J")  # Clear screen
            print(monitor.format_report())
            print("\nPress Ctrl+C to stop...")
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped.")
