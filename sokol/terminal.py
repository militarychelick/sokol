# -*- coding: utf-8 -*-
"""
SOKOL v7 — Terminal & System Dashboard
TerminalExecutor (PowerShell), SystemDashboard (GPU/CPU/RAM + Event Viewer)
"""
import os
import subprocess
import platform
from .config import NOWINDOW, HAS_PSUTIL
from .core import INTERRUPT
class TerminalExecutor:
    """
    Direct PowerShell command execution.
    Runs commands and returns output without opening a window.
    """
    @classmethod
    def run_powershell(cls, command, timeout=30):
        """Execute a PowerShell command and return output."""
        INTERRUPT.check()
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-Command", command,
                ],
                capture_output=True, text=True,
                timeout=timeout, creationflags=NOWINDOW,
                encoding="utf-8", errors="replace",
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0
            output = stdout if stdout else stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, f"PowerShell timed out after {timeout}s."
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"PowerShell error: {e}"
    @classmethod
    def run_cmd(cls, command, timeout=30):
        """Execute a CMD command and return output."""
        INTERRUPT.check()
        try:
            result = subprocess.run(
                ["cmd", "/c", command],
                capture_output=True, text=True,
                timeout=timeout, creationflags=NOWINDOW,
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            return result.returncode == 0, stdout if stdout else stderr
        except subprocess.TimeoutExpired:
            return False, f"CMD timed out after {timeout}s."
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"CMD error: {e}"
    @classmethod
    def run_interactive(cls, commands, timeout=60):
        """Run multiple commands sequentially in PowerShell."""
        full_cmd = "; ".join(commands)
        return cls.run_powershell(full_cmd, timeout=timeout)
class SystemDashboard:
    """
    Extended system diagnostics.
    CPU, GPU, RAM details + Event Viewer critical errors.
    """
    @classmethod
    def get_full_report(cls):
        """Generate comprehensive system dashboard."""
        lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        lines.append("   SOKOL v7 — System Dashboard")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        # OS Info
        lines.append(f"  OS:       {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"  Host:     {platform.node()}")
        lines.append(f"  Arch:     {platform.machine()}")
        lines.append("")
        # CPU
        cpu_info = cls._get_cpu_info()
        if cpu_info:
            lines.append("  ── CPU ──")
            for k, v in cpu_info.items():
                lines.append(f"    {k}: {v}")
            lines.append("")
        # GPU
        gpu_info = cls._get_gpu_info()
        if gpu_info:
            lines.append("  ── GPU ──")
            for k, v in gpu_info.items():
                lines.append(f"    {k}: {v}")
            lines.append("")
        # RAM
        ram_info = cls._get_ram_info()
        if ram_info:
            lines.append("  ── RAM ──")
            for k, v in ram_info.items():
                lines.append(f"    {k}: {v}")
            lines.append("")
        # Top processes
        top = cls._get_top_processes()
        if top:
            lines.append("  ── Top Processes (by CPU) ──")
            for p in top[:8]:
                lines.append(f"    {p}")
            lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    @classmethod
    def get_event_viewer_errors(cls, count=15):
        """Fetch critical errors from Windows Event Viewer."""
        INTERRUPT.check()
        ps_cmd = (
            f"Get-WinEvent -LogName System -FilterXPath "
            f"\"*[System[(Level=1 or Level=2)]]\" "
            f"-MaxEvents {count} 2>$null | "
            f"Format-Table -Property TimeCreated, Id, Message -AutoSize -Wrap"
        )
        ok, output = TerminalExecutor.run_powershell(ps_cmd, timeout=20)
        if ok and output:
            return f"━━━ Event Viewer — Critical/Error (last {count}) ━━━\n{output}\n━━━━━━━━━━━━━━"
        # Fallback
        ps_cmd2 = (
            f"Get-EventLog -LogName System -EntryType Error -Newest {count} 2>$null | "
            f"Format-Table -Property TimeGenerated, EventID, Message -AutoSize -Wrap"
        )
        ok2, output2 = TerminalExecutor.run_powershell(ps_cmd2, timeout=20)
        if ok2 and output2:
            return f"━━━ System Errors (last {count}) ━━━\n{output2}\n━━━━━━━━━━━━━━"
        return "Could not read Event Viewer (may require admin rights)."
    @classmethod
    def _get_cpu_info(cls):
        info = {}
        if HAS_PSUTIL:
            import psutil
            info["Usage"] = f"{psutil.cpu_percent(interval=0.5)}%"
            info["Cores"] = f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical"
            freq = psutil.cpu_freq()
            if freq:
                info["Frequency"] = f"{freq.current:.0f} MHz (max {freq.max:.0f} MHz)"
        else:
            try:
                ok, out = TerminalExecutor.run_powershell(
                    "Get-CimInstance Win32_Processor | "
                    "Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, "
                    "CurrentClockSpeed, MaxClockSpeed, LoadPercentage | Format-List",
                    timeout=10,
                )
                if ok:
                    for line in out.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            info[k.strip()] = v.strip()
            except Exception:
                pass
        # Get CPU name
        try:
            ok, name = TerminalExecutor.run_powershell(
                "(Get-CimInstance Win32_Processor).Name", timeout=5,
            )
            if ok and name:
                info["Model"] = name.strip()
        except Exception:
            pass
        return info
    @classmethod
    def _get_gpu_info(cls):
        info = {}
        try:
            ok, out = TerminalExecutor.run_powershell(
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, DriverVersion, AdapterRAM, Status | Format-List",
                timeout=10,
            )
            if ok:
                for line in out.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k == "AdapterRAM" and v.isdigit():
                            v = f"{int(v) / (1024**3):.1f} GB"
                        info[k] = v
        except Exception:
            pass
        # Try ROCm smi for AMD
        try:
            ok, out = TerminalExecutor.run_cmd("rocm-smi --showuse --showtemp 2>nul", timeout=10)
            if ok and out:
                info["ROCm"] = out[:200]
        except Exception:
            pass
        return info
    @classmethod
    def _get_ram_info(cls):
        info = {}
        if HAS_PSUTIL:
            import psutil
            m = psutil.virtual_memory()
            info["Total"] = f"{m.total / (1024**3):.1f} GB"
            info["Used"] = f"{m.used / (1024**3):.1f} GB ({m.percent}%)"
            info["Available"] = f"{m.available / (1024**3):.1f} GB"
            sw = psutil.swap_memory()
            info["Swap"] = f"{sw.used / (1024**3):.1f} / {sw.total / (1024**3):.1f} GB"
        else:
            try:
                ok, out = TerminalExecutor.run_powershell(
                    "$os = Get-CimInstance Win32_OperatingSystem; "
                    "\"Total: $([math]::Round($os.TotalVisibleMemorySize/1MB,1)) GB, "
                    "Free: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB\"",
                    timeout=10,
                )
                if ok:
                    info["Memory"] = out.strip()
            except Exception:
                pass
        return info
    @classmethod
    def _get_top_processes(cls):
        if HAS_PSUTIL:
            import psutil
            procs = []
            for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    procs.append((info["cpu_percent"] or 0, info["memory_percent"] or 0, info["name"]))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            procs.sort(key=lambda x: -x[0])
            return [
                f"{name:<30} CPU: {cpu:5.1f}%  RAM: {mem:5.1f}%"
                for cpu, mem, name in procs[:10] if cpu > 0
            ]
        else:
            try:
                ok, out = TerminalExecutor.run_powershell(
                    "Get-Process | Sort-Object CPU -Descending | "
                    "Select-Object -First 10 Name, CPU, "
                    "@{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
                    "Format-Table -AutoSize",
                    timeout=10,
                )
                if ok:
                    return out.splitlines()[:12]
            except Exception:
                pass
        return []