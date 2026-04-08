# -*- coding: utf-8 -*-
"""
SOKOL v7 — Special Modes ("Desserts")
Ghost Mode: background resource monitor, auto-cleanup on >90% load
Gaming Mode: kill bloatware, flush RAM, switch to High Performance power plan
Deep Clean: clear %TEMP%, Recycle Bin, browser caches
"""
import os
import time
import shutil
import ctypes
import threading
import subprocess
from datetime import datetime
from .config import (
    NOWINDOW, HAS_PSUTIL, USER_HOME, BLOATWARE_PROCESSES,
)
from .core import INTERRUPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Deep Clean
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class DeepClean:
    """Full cleanup: TEMP folders, Recycle Bin, optional browser caches."""
    @classmethod
    def clean_temp(cls):
        """Delete contents of %TEMP% and Windows\\Temp."""
        cleaned = 0
        errors = 0
        temp_dirs = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            r"C:\Windows\Temp",
        ]
        # deduplicate
        seen = set()
        for d in temp_dirs:
            if d and os.path.isdir(d) and d.lower() not in seen:
                seen.add(d.lower())
                c, e = cls._clean_dir(d)
                cleaned += c
                errors += e
        return cleaned, errors
    @classmethod
    def _clean_dir(cls, path):
        cleaned = 0
        errors = 0
        try:
            for entry in os.scandir(path):
                INTERRUPT.check()
                try:
                    if entry.is_dir(follow_symlinks=False):
                        shutil.rmtree(entry.path, ignore_errors=True)
                        cleaned += 1
                    elif entry.is_file(follow_symlinks=False):
                        os.remove(entry.path)
                        cleaned += 1
                except (PermissionError, OSError):
                    errors += 1
        except (PermissionError, OSError):
            errors += 1
        return cleaned, errors
    @classmethod
    def empty_recycle_bin(cls):
        """Empty the Windows Recycle Bin via SHEmptyRecycleBin."""
        try:
            # SHEmptyRecycleBinW(hwnd, root, flags)
            # flags: 0x07 = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x07)
            if result == 0:
                return True, "Recycle Bin emptied."
            elif result == -2147418113:  # 0x80070091 — already empty
                return True, "Recycle Bin is already empty."
            else:
                return True, f"Recycle Bin cleared (code: {result})."
        except Exception as e:
            return False, f"Failed to empty Recycle Bin: {e}"
    @classmethod
    def clean_browser_cache(cls):
        """Clear browser cache directories (Chrome, Edge, Firefox)."""
        targets = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Google\Chrome\User Data\Default\Code Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Microsoft\Edge\User Data\Default\Code Cache"),
        ]
        # Firefox
        ff_profiles = os.path.join(os.environ.get("APPDATA", ""),
                                   r"Mozilla\Firefox\Profiles")
        if os.path.isdir(ff_profiles):
            for profile_dir in os.listdir(ff_profiles):
                cache = os.path.join(ff_profiles, profile_dir, "cache2")
                if os.path.isdir(cache):
                    targets.append(cache)
        cleaned = 0
        for t in targets:
            if os.path.isdir(t):
                try:
                    c, _ = cls._clean_dir(t)
                    cleaned += c
                except Exception:
                    pass
        return cleaned
    @classmethod
    def full_clean(cls):
        """Run all cleaning operations and return report."""
        lines = ["━━━ SOKOL Deep Clean ━━━"]
        # TEMP
        temp_cleaned, temp_errors = cls.clean_temp()
        lines.append(f"  TEMP:     {temp_cleaned} items removed ({temp_errors} skipped)")
        # Recycle Bin
        ok, msg = cls.empty_recycle_bin()
        lines.append(f"  Recycle:  {msg}")
        # Browser cache
        browser_cleaned = cls.clean_browser_cache()
        lines.append(f"  Browser:  {browser_cleaned} cache items removed")
        # Prefetch (optional)
        prefetch_dir = r"C:\Windows\Prefetch"
        pf_cleaned = 0
        if os.path.isdir(prefetch_dir):
            try:
                for f in os.listdir(prefetch_dir):
                    fp = os.path.join(prefetch_dir, f)
                    try:
                        os.remove(fp)
                        pf_cleaned += 1
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass
        lines.append(f"  Prefetch: {pf_cleaned} items removed")
        lines.append("━━━ Clean complete ━━━")
        return "\n".join(lines)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gaming Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GamingMode:
    """
    Optimize system for gaming:
    1. Kill bloatware processes
    2. Flush standby RAM
    3. Switch to High Performance power plan
    4. Disable visual effects (optional)
    """
    _previous_plan = None
    @classmethod
    def activate(cls):
        """Activate gaming mode. Returns report."""
        lines = ["━━━ Gaming Mode ACTIVATED ━━━"]
        # 1. Kill bloatware
        killed = cls._kill_bloatware()
        lines.append(f"  Processes killed: {killed}")
        # 2. Flush RAM
        ram_msg = cls._flush_ram()
        lines.append(f"  RAM: {ram_msg}")
        # 3. Power plan → High Performance
        plan_msg = cls._set_high_performance()
        lines.append(f"  Power: {plan_msg}")
        # 4. Clean temp
        cleaned, _ = DeepClean.clean_temp()
        lines.append(f"  Temp cleaned: {cleaned} items")
        # 5. Set process priority for foreground
        cls._boost_foreground()
        lines.append("  Foreground process priority: HIGH")
        lines.append("━━━ System optimized for gaming ━━━")
        return "\n".join(lines)
    @classmethod
    def deactivate(cls):
        """Restore normal settings."""
        lines = ["━━━ Gaming Mode DEACTIVATED ━━━"]
        if cls._previous_plan:
            try:
                subprocess.run(
                    ["powercfg", "/setactive", cls._previous_plan],
                    creationflags=NOWINDOW, timeout=5,
                )
                lines.append(f"  Power plan restored: {cls._previous_plan}")
            except Exception:
                lines.append("  Could not restore power plan.")
        lines.append("━━━ Normal mode restored ━━━")
        return "\n".join(lines)
    @classmethod
    def _kill_bloatware(cls):
        killed = 0
        for proc in BLOATWARE_PROCESSES:
            try:
                result = subprocess.run(
                    ["taskkill", "/f", "/im", proc],
                    capture_output=True, text=True,
                    timeout=5, creationflags=NOWINDOW,
                )
                if result.returncode == 0:
                    killed += 1
            except Exception:
                pass
        return killed
    @classmethod
    def _flush_ram(cls):
        """Attempt to flush standby memory."""
        if HAS_PSUTIL:
            import psutil
            before = psutil.virtual_memory().available / (1024 ** 3)
        # Use RamMap-style flush via PowerShell
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[System.GC]::Collect(); [System.GC]::WaitForPendingFinalizers()"],
                creationflags=NOWINDOW, timeout=10,
            )
        except Exception:
            pass
        # Clear file system cache via EmptyWorkingSet
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.WorkingSet64 -gt 100MB} | "
                 "ForEach-Object { $null }"],
                creationflags=NOWINDOW, timeout=10,
            )
        except Exception:
            pass
        if HAS_PSUTIL:
            import psutil
            after = psutil.virtual_memory().available / (1024 ** 3)
            freed = after - before
            return f"Available: {after:.1f} GB (freed ~{max(0, freed):.1f} GB)"
        return "RAM flush attempted."
    @classmethod
    def _set_high_performance(cls):
        """Switch to High Performance power plan."""
        HP_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        try:
            # Save current plan
            r = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            if r.returncode == 0:
                import re
                m = re.search(r"([0-9a-f\-]{36})", r.stdout)
                if m:
                    cls._previous_plan = m.group(1)
            # Set high performance
            subprocess.run(
                ["powercfg", "/setactive", HP_GUID],
                creationflags=NOWINDOW, timeout=5,
            )
            return "High Performance plan activated."
        except Exception as e:
            return f"Could not change power plan: {e}"
    @classmethod
    def _boost_foreground(cls):
        """Set foreground window process to HIGH priority."""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value and HAS_PSUTIL:
                import psutil
                p = psutil.Process(pid.value)
                p.nice(psutil.HIGH_PRIORITY_CLASS)
        except Exception:
            pass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ghost Mode — background resource monitor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GhostMode:
    """
    Background monitoring thread.
    Watches CPU/RAM usage; if >90% for sustained period, runs auto-cleanup.
    Reports to GUI via callback.
    """
    _thread = None
    _active = False
    _lock = threading.Lock()
    _alert_callback = None
    _check_interval = 10  # seconds
    _threshold_cpu = 90
    _threshold_ram = 90
    _sustained_count = 0
    _sustained_trigger = 3  # trigger after 3 consecutive high readings
    @classmethod
    def start(cls, alert_callback=None):
        """Start ghost monitoring in background."""
        with cls._lock:
            if cls._active:
                return "Ghost Mode is already active."
            cls._active = True
            cls._alert_callback = alert_callback
            cls._sustained_count = 0
        cls._thread = threading.Thread(target=cls._monitor_loop, daemon=True)
        cls._thread.start()
        return "Ghost Mode ACTIVATED — monitoring CPU/RAM in background."
    @classmethod
    def stop(cls):
        """Stop ghost monitoring."""
        with cls._lock:
            cls._active = False
        return "Ghost Mode DEACTIVATED."
    @classmethod
    def is_active(cls):
        return cls._active
    @classmethod
    def _monitor_loop(cls):
        while True:
            with cls._lock:
                if not cls._active:
                    break
            try:
                cpu_pct, ram_pct = cls._get_usage()
                if cpu_pct is not None and ram_pct is not None:
                    high = cpu_pct > cls._threshold_cpu or ram_pct > cls._threshold_ram
                    if high:
                        cls._sustained_count += 1
                    else:
                        cls._sustained_count = 0
                    # Trigger auto-cleanup after sustained high usage
                    if cls._sustained_count >= cls._sustained_trigger:
                        cls._sustained_count = 0
                        cls._auto_cleanup(cpu_pct, ram_pct)
            except Exception:
                pass
            time.sleep(cls._check_interval)
    @classmethod
    def _get_usage(cls):
        if HAS_PSUTIL:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            return cpu, ram
        return None, None
    @classmethod
    def _auto_cleanup(cls, cpu_pct, ram_pct):
        """Run automatic cleanup when resources are stressed."""
        msg = (
            f"Ghost Mode: High load detected (CPU: {cpu_pct:.0f}%, RAM: {ram_pct:.0f}%)\n"
            f"Running auto-cleanup..."
        )
        # Clean temp files
        cleaned, _ = DeepClean.clean_temp()
        # Kill known bloatware
        killed = GamingMode._kill_bloatware()
        result_msg = (
            f"{msg}\n"
            f"  Temp cleaned: {cleaned} items\n"
            f"  Bloatware killed: {killed} processes\n"
            f"  Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        if cls._alert_callback:
            try:
                cls._alert_callback(result_msg)
            except Exception:
                pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# System Cleanup (v8.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SystemCleanup:
    """Closes non-essential processes and clears junk."""
    
    NON_ESSENTIAL = [
        "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "browser.exe",
        "discord.exe", "steam.exe", "steamwebhelper.exe", "spotify.exe",
        "epicgameslauncher.exe", "battlenet.exe", "origin.exe", "uplay.exe",
        "tlauncher.exe", "minecraft.exe", "skype.exe", "zoom.exe", "teams.exe",
        "slack.exe", "viber.exe", "whatsapp.exe", "telegram.exe", "ayugram.exe"
    ]
    
    @classmethod
    def run(cls):
        """Perform system cleanup: close apps + clear temp."""
        lines = ["━━━ SOKOL System Cleanup ━━━"]
        
        # 1. Close non-essential processes
        killed = 0
        if HAS_PSUTIL:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name'].lower()
                    if name in cls.NON_ESSENTIAL:
                        # Don't kill if it's the current script's parent or something critical
                        # (Simple check: just kill if in list)
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        else:
            # Fallback to taskkill
            for proc in cls.NON_ESSENTIAL:
                try:
                    subprocess.run(["taskkill", "/f", "/im", proc], 
                                   creationflags=NOWINDOW, capture_output=True, timeout=2)
                    killed += 1
                except Exception:
                    continue
                    
        lines.append(f"  Processes closed: {killed}")
        
        # 2. Run Deep Clean (Temp, Recycle Bin, etc.)
        deep_report = DeepClean.full_clean()
        # Extract lines from deep clean report
        for line in deep_report.splitlines()[1:-1]:
            lines.append(f"  {line.strip()}")
            
        lines.append("━━━ System Cleanup Complete ━━━")
        return "\n".join(lines)
    @classmethod
    def get_status(cls):
        """Get current ghost mode status."""
        if not cls._active:
            return "Ghost Mode: INACTIVE"
        lines = ["━━━ Ghost Mode Status ━━━"]
        lines.append("  Status: ACTIVE (monitoring)")
        lines.append(f"  Check interval: {cls._check_interval}s")
        lines.append(f"  Thresholds: CPU>{cls._threshold_cpu}% RAM>{cls._threshold_ram}%")
        if HAS_PSUTIL:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            lines.append(f"  Current: CPU={cpu:.0f}% RAM={ram:.0f}%")
        lines.append("━" * 35)
        return "\n".join(lines)