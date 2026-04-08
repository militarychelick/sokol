# -*- coding: utf-8 -*-
"""
SOKOL v8.0 — System Tools & Utilities
Fixed: SmartLauncher brings to front if already running.
Fixed: ProcessKiller uses aggressive force-kill.
New: WindowFocuser, QuickNote integration.
"""
import os
import re
import io
import csv
import time
import shutil
import string
import ctypes
import difflib
import platform
import subprocess
import webbrowser
import urllib.request
from datetime import datetime

from ..config import (
    NOWINDOW, HAS_PSUTIL, USER_HOME, SCREENSHOTS_DIR,
    RUS_APP_MAP, RUS_PROCESS_MAP, FOLDER_ALIASES,
    SYSTEM_TOOLS, WEB_SERVICES,
)
from ..core import INTERRUPT


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WindowFocuser — bring existing window to front
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WindowFocuser:
    """Find a running app's window and bring it to the foreground."""

    @classmethod
    def find_window_by_process(cls, process_name):
        """
        Find visible windows belonging to a process name.
        Returns list of (hwnd, title).
        """
        results = []
        pname = process_name.lower().replace(".exe", "")

        # Get PIDs for matching process
        pids = set()
        try:
            r = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            for row in csv.reader(io.StringIO(r.stdout)):
                if len(row) >= 2:
                    name = row[0].strip().lower().replace(".exe", "")
                    if pname in name or name in pname:
                        try:
                            pids.add(int(row[1].strip()))
                        except ValueError:
                            pass
        except Exception:
            pass

        if not pids:
            return results

        # Enumerate windows and match by PID
        def callback(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(
                    hwnd, ctypes.byref(pid)
                )
                if pid.value in pids:
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.strip()
                        if title:
                            results.append((hwnd, title))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
        return results

    @classmethod
    def bring_to_front(cls, process_name):
        """
        Try to bring an existing window of the process to the foreground.
        Returns (success, message).
        """
        windows = cls.find_window_by_process(process_name)
        if not windows:
            return False, None

        hwnd, title = windows[0]
        try:
            user32 = ctypes.windll.user32
            # Restore if minimized
            SW_RESTORE = 9
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            # Bring to front
            user32.SetForegroundWindow(hwnd)
            return True, f"Brought to front: {title}"
        except Exception:
            # Fallback: use Alt trick to steal focus
            try:
                user32 = ctypes.windll.user32
                user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 0x0002, 0)  # Alt up
                return True, f"Brought to front: {title}"
            except Exception:
                return False, None

    @classmethod
    def is_running(cls, process_name):
        """Check if a process with this name is running."""
        pname = process_name.lower().replace(".exe", "").strip()
        try:
            r = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            for row in csv.reader(io.StringIO(r.stdout)):
                if len(row) >= 1:
                    name = row[0].strip().lower().replace(".exe", "")
                    if pname == name or pname in name or name in pname:
                        return True
        except Exception:
            pass
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SystemTools
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SystemTools:
    """Launch standard Windows system utilities."""

    @classmethod
    def launch(cls, name):
        key = name.lower().strip()
        exe = SYSTEM_TOOLS.get(key)
        if not exe:
            for tool_name, tool_exe in SYSTEM_TOOLS.items():
                if key in tool_name or tool_name in key:
                    exe = tool_exe
                    break
        if exe:
            try:
                if exe.endswith(".msc"):
                    subprocess.Popen(["mmc", exe], creationflags=NOWINDOW)
                elif exe.endswith(".cpl"):
                    subprocess.Popen(["control", exe], creationflags=NOWINDOW)
                else:
                    os.startfile(exe)
                return True, f"Launched: {name} ({exe})"
            except Exception as e:
                return False, f"Failed to launch {name}: {e}"
        return False, None

    @classmethod
    def is_system_tool(cls, name):
        key = name.lower().strip()
        if key in SYSTEM_TOOLS:
            return True
        for tool_name in SYSTEM_TOOLS:
            if key in tool_name or tool_name in key:
                return True
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SmartLauncher — with bring-to-front support
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SmartLauncher:
    """
    Dynamic app discovery + smart launch.
    v8.0: If app is already running, brings its window to front
    instead of launching a duplicate.
    """

    _index = None
    _index_time = 0
    _cache = {}
    INDEX_TTL = 600
    JUNK = {
        ".git", "node_modules", "__pycache__", "cache", ".cache",
        "temp", "tmp", "backup", "$recycle.bin",
        "system volume information", ".venv", "venv", "site-packages",
        "windows", "system32", "syswow64", "winsxs",
    }

    @classmethod
    def _scan_dirs(cls):
        ev = os.path.expandvars
        dirs = []
        cands = [
            ev(r"%PROGRAMFILES%"), ev(r"%PROGRAMFILES(X86)%"),
            ev(r"%LOCALAPPDATA%"), ev(r"%LOCALAPPDATA%\Programs"),
            ev(r"%APPDATA%"),
            os.path.join(USER_HOME, "Desktop"),
            os.path.join(USER_HOME, "OneDrive", "Desktop"), # OneDrive Desktop support
            os.path.join(USER_HOME, "Documents"),
            os.path.join(USER_HOME, "Downloads"),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            ev(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            ev(r"%LOCALAPPDATA%\Microsoft\WindowsApps"),
            USER_HOME,
            os.path.join(USER_HOME, "OneDrive", "Desktop", "AyiuGram"), # Specific AyuGram path
            r"C:\Users\vapcbuild\OneDrive\Desktop\AyiuGram", # Absolute path just in case
        ]
        for letter in string.ascii_uppercase:
            if letter == "C":
                continue
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                dirs.append(drive)
                for sub in ["Games", "Programs", "Apps", "Portable",
                            "Software", "Program Files", "SteamLibrary",
                            "GOG Games", "Epic Games"]:
                    p = os.path.join(drive, sub)
                    if os.path.isdir(p):
                        cands.append(p)
        for p in cands:
            if p and os.path.isdir(p) and p not in dirs:
                dirs.append(p)
        return dirs

    @classmethod
    def _build_index(cls, force=False):
        now = time.time()
        if cls._index is not None and not force and (now - cls._index_time) < cls.INDEX_TTL:
            return
        index = {}
        exts = (".exe", ".lnk", ".url")
        for root_dir in cls._scan_dirs():
            INTERRUPT.check()
            depth_limit = 3 if len(root_dir) <= 3 else 7
            try:
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    INTERRUPT.check()
                    depth = dirpath.replace(root_dir, "").count(os.sep)
                    if depth > depth_limit:
                        dirnames.clear()
                        continue
                    dirnames[:] = [d for d in dirnames if d.lower() not in cls.JUNK]
                    for fname in filenames:
                        fl = fname.lower()
                        if not fl.endswith(exts):
                            continue
                        stem = os.path.splitext(fl)[0]
                        full = os.path.join(dirpath, fname)
                        if stem not in index:
                            index[stem] = []
                        pri = 0 if fl.endswith(".lnk") else (1 if fl.endswith(".exe") else 2)
                        index[stem].append((pri, full))
            except InterruptedError:
                raise
            except (PermissionError, OSError):
                continue
        for stem in index:
            index[stem].sort(key=lambda x: x[0])
        cls._index = index
        cls._index_time = now

    @classmethod
    def _translate(cls, query):
        q = query.lower().strip()
        for rus, eng in RUS_APP_MAP.items():
            if rus in q:
                return eng
        return q

    @classmethod
    def _get_exe_name(cls, path):
        """Extract process name from a path for bring-to-front check."""
        fname = os.path.basename(path).lower()
        if fname.endswith(".lnk") or fname.endswith(".url"):
            return os.path.splitext(fname)[0]
        return fname.replace(".exe", "")

    @classmethod
    def find(cls, query):
        cls._build_index()
        q = cls._translate(query).lower().replace(".exe", "").strip()
        results = []
        seen = set()
        for stem, entries in cls._index.items():
            best_path = entries[0][1]
            if best_path.lower() in seen:
                continue
            if stem == q:
                score = 0
            elif stem.startswith(q) or q.startswith(stem):
                score = 1
            elif q in stem:
                score = 2
            elif stem in q:
                score = 3
            else:
                try:
                    from rapidfuzz import fuzz

                    if max(fuzz.ratio(q, stem), fuzz.partial_ratio(q, stem)) >= 80:
                        score = 4
                    else:
                        continue
                except ImportError:
                    ratio = difflib.SequenceMatcher(None, q, stem).ratio()
                    if ratio > 0.75:
                        score = 4
                    else:
                        continue
            seen.add(best_path.lower())
            results.append((score, best_path))
        results.sort(key=lambda x: x[0])
        return results

    @classmethod
    def launch(cls, app_name):
        """
        Smart launch:
        1. Check if already running → bring to front
        2. Check cache → launch from cache
        3. Try Steam launch for games
        4. Search filesystem → launch best match
        """
        translated = cls._translate(app_name)
        
        # v8.0.7: FAST TRACK for common apps to avoid full filesystem scan
        fast_paths = {
            "telegram": [
                os.path.join(USER_HOME, "AppData", "Roaming", "Telegram Desktop", "Telegram.exe"),
                os.path.join(os.environ.get("PROGRAMFILES", "C:\Program Files"), "Telegram Desktop", "Telegram.exe"),
            ],
            "ayugram": [
                os.path.join(USER_HOME, "OneDrive", "Desktop", "AyiuGram", "AyuGram.exe"),
                os.path.join(USER_HOME, "Desktop", "AyiuGram", "AyuGram.exe"),
                r"C:\Users\vapcbuild\OneDrive\Desktop\AyiuGram\AyuGram.exe",
            ]
        }
        
        app_key = translated.lower().strip()
        if app_key in fast_paths:
            # Check if running first
            ok_f, msg_f = WindowFocuser.bring_to_front(app_key)
            if ok_f: return True, msg_f, None
            
            # Try fast paths
            for p in fast_paths[app_key]:
                if os.path.exists(p):
                    try:
                        os.startfile(p)
                        return True, f"Launched (fast path): {p}", p
                    except Exception:
                        continue

        # Step 1: Check if already running and bring to front
        ok, msg = WindowFocuser.bring_to_front(translated)
        if ok:
            return True, f"Already running. {msg}", None

        # Also check the original name
        if translated != app_name.lower().strip():
            ok, msg = WindowFocuser.bring_to_front(app_name)
            if ok:
                return True, f"Already running. {msg}", None

        # Step 2: Check cache
        cache_key = app_name.lower().strip()
        if cache_key in cls._cache:
            cached = cls._cache[cache_key]
            if os.path.exists(cached):
                try:
                    os.startfile(cached)
                    return True, f"Launched (cached): {cached}", cached
                except Exception:
                    del cls._cache[cache_key]

        # Step 3: Try Steam launch for games (v8.0)
        from ..steam_helper import SteamHelper
        is_steam, appid = SteamHelper.is_steam_game(app_name)
        if is_steam and appid:
            ok, msg = SteamHelper.launch_steam_game(appid)
            if ok:
                return True, f"Launched via Steam: {app_name} (AppID: {appid})", None

        # Step 4: Search filesystem
        results = cls.find(app_name)
        if results:
            best = results[0][1]
            try:
                os.startfile(best)
                cls._cache[cache_key] = best
                return True, f"Launched: {best}", best
            except Exception as e:
                return False, f"Found but failed: {best}\nError: {e}", None

        # Step 5: If it's a known non-Steam game, provide helpful info
        steam_info = SteamHelper.get_game_info(app_name)
        if "not available on Steam" in steam_info or "via" in steam_info:
            return False, f"{steam_info}\n\nTry launching the game's own launcher first.", None

        return False, f"Could not find '{app_name}'.\nTry installing it or check the name.", None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ProcessKiller — enhanced force-kill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProcessKiller:
    """
    Kill processes with aggressive force.
    v8.0: Uses both taskkill /F /PID and taskkill /F /IM for reliability.
    Falls back to psutil.kill() if available.
    """

    @classmethod
    def _translate(cls, query):
        q = query.lower().strip()
        for rus, eng in RUS_PROCESS_MAP.items():
            if rus in q:
                return eng
        return q

    @classmethod
    def get_running(cls):
        try:
            r = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            procs = []
            for row in csv.reader(io.StringIO(r.stdout)):
                if len(row) >= 2:
                    try:
                        procs.append((row[0].strip(), int(row[1].strip())))
                    except ValueError:
                        continue
            return procs
        except Exception:
            return []

    @classmethod
    def find(cls, query):
        query = cls._translate(query)
        q = query.lower().replace(".exe", "").strip()
        procs = cls.get_running()
        exact, starts, contains, fuzzy = [], [], [], []
        seen = set()
        for name, pid in procs:
            nl = name.lower()
            stem = nl.replace(".exe", "")
            if nl in seen:
                continue
            if stem == q:
                exact.append((name, pid)); seen.add(nl)
            elif stem.startswith(q) or q.startswith(stem):
                starts.append((name, pid)); seen.add(nl)
            elif q in stem:
                contains.append((name, pid)); seen.add(nl)
            else:
                ratio = difflib.SequenceMatcher(None, q, stem).ratio()
                if ratio > 0.55:
                    fuzzy.append((name, pid, ratio))
        fuzzy.sort(key=lambda x: -x[2])
        fuzzy_clean = [(n, p) for n, p, _ in fuzzy if n.lower() not in seen]
        return exact + starts + contains + fuzzy_clean

    @classmethod
    def kill(cls, query):
        """
        Aggressively kill all matching processes.
        Uses multiple methods for reliability.
        """
        matches = cls.find(query)
        if not matches:
            return False, f"No process found matching '{query}'."

        killed, failed = [], []
        killed_names = set()

        for name, pid in matches:
            INTERRUPT.check()
            if name.lower() in killed_names:
                continue

            success = False

            # Method 1: taskkill /F /PID (force kill by PID)
            try:
                r = subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True, text=True, timeout=8,
                    creationflags=NOWINDOW,
                )
                if r.returncode == 0:
                    success = True
            except Exception:
                pass

            # Method 2: taskkill /F /IM (force kill by image name)
            if not success:
                try:
                    r = subprocess.run(
                        ["taskkill", "/F", "/IM", name],
                        capture_output=True, text=True, timeout=8,
                        creationflags=NOWINDOW,
                    )
                    if r.returncode == 0:
                        success = True
                except Exception:
                    pass

            # Method 3: psutil force kill
            if not success and HAS_PSUTIL:
                try:
                    import psutil
                    p = psutil.Process(pid)
                    p.kill()
                    p.wait(timeout=3)
                    success = True
                except Exception:
                    pass

            # Method 4: wmic process delete
            if not success:
                try:
                    r = subprocess.run(
                        ["wmic", "process", "where", f"ProcessId={pid}", "delete"],
                        capture_output=True, text=True, timeout=8,
                        creationflags=NOWINDOW,
                    )
                    if r.returncode == 0:
                        success = True
                except Exception:
                    pass

            if success:
                killed.append(f"{name} (PID {pid})")
                killed_names.add(name.lower())
            else:
                failed.append(f"{name} (PID {pid})")

        if killed:
            msg = "Closed: " + ", ".join(killed)
            if failed:
                msg += "\nFailed: " + ", ".join(failed)
            return True, msg
        return False, "Failed to close: " + ", ".join(failed)

    @classmethod
    def kill_by_name(cls, image_name):
        """Kill all processes with exact image name (e.g. 'chrome.exe')."""
        if not image_name.endswith(".exe"):
            image_name += ".exe"
        try:
            r = subprocess.run(
                ["taskkill", "/F", "/IM", image_name],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            if r.returncode == 0:
                return True, f"Killed all {image_name} processes."
            return False, r.stderr.strip() or f"No {image_name} processes found."
        except Exception as e:
            return False, f"Kill error: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WebRouter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WebRouter:
    @classmethod
    def open_service(cls, name):
        nl = name.lower().strip()
        if nl.startswith(("http://", "https://", "www.")):
            url = nl if nl.startswith("http") else "https://" + nl
            webbrowser.open(url)
            return True, f"Opened: {url}"
        for svc, url in WEB_SERVICES.items():
            if svc == nl or svc in nl or nl in svc:
                webbrowser.open(url)
                return True, f"Opened {svc}: {url}"
        if re.match(r"^[\w\-]+\.\w{2,}$", nl):
            webbrowser.open(f"https://{nl}")
            return True, f"Opened: https://{nl}"
        return False, f"Unknown web service: {name}"

    @classmethod
    def web_search(cls, query):
        url = f"https://www.google.com/search?q={urllib.request.quote(query)}"
        webbrowser.open(url)
        return True, f"Searching Google: {query}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MediaController
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MediaController:
    _MUTE, _DOWN, _UP = 0xAD, 0xAE, 0xAF
    _NEXT, _PREV, _STOP, _PLAY = 0xB0, 0xB1, 0xB2, 0xB3
    _EXT, _KEYUP = 0x0001, 0x0002

    @classmethod
    def _press(cls, vk):
        ctypes.windll.user32.keybd_event(vk, 0, cls._EXT, 0)
        ctypes.windll.user32.keybd_event(vk, 0, cls._EXT | cls._KEYUP, 0)

    @classmethod
    def mute(cls):
        # v8.0 Fix: Do not check for process, just send global VK_VOLUME_MUTE
        cls._press(cls._MUTE); return "Toggled global mute."
    @classmethod
    def volume_up(cls, steps=5):
        for _ in range(steps): cls._press(cls._UP)
        return f"Volume up (+{steps*2}%)."
    @classmethod
    def volume_down(cls, steps=5):
        for _ in range(steps): cls._press(cls._DOWN)
        return f"Volume down (-{steps*2}%)."
    @classmethod
    def set_volume(cls, pct):
        pct = max(0, min(100, int(pct)))
        for _ in range(50): cls._press(cls._DOWN)
        for _ in range(pct // 2): cls._press(cls._UP)
        return f"Volume set to ~{pct}%."
    @classmethod
    def play_pause(cls):
        cls._press(cls._PLAY); return "Play/Pause toggled."
    @classmethod
    def next_track(cls):
        cls._press(cls._NEXT); return "Next track."
    @classmethod
    def prev_track(cls):
        cls._press(cls._PREV); return "Previous track."
    @classmethod
    def stop(cls):
        cls._press(cls._STOP); return "Stopped."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PowerController
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PowerController:
    @classmethod
    def lock(cls):
        ctypes.windll.user32.LockWorkStation(); return "Screen locked."
    @classmethod
    def shutdown(cls, delay=0):
        subprocess.Popen(["shutdown", "/s", "/t", str(delay)], creationflags=NOWINDOW)
        return f"Shutting down in {delay}s..."
    @classmethod
    def restart(cls, delay=0):
        subprocess.Popen(["shutdown", "/r", "/t", str(delay)], creationflags=NOWINDOW)
        return f"Restarting in {delay}s..."
    @classmethod
    def cancel_shutdown(cls):
        subprocess.Popen(["shutdown", "/a"], creationflags=NOWINDOW)
        return "Shutdown/restart cancelled."
    @classmethod
    def sleep(cls):
        try:
            ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
        except Exception:
            subprocess.Popen(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                creationflags=NOWINDOW,
            )
        return "Going to sleep..."
    @classmethod
    def hibernate(cls):
        try:
            ctypes.windll.PowrProf.SetSuspendState(1, 1, 0)
        except Exception:
            subprocess.Popen(["shutdown", "/h"], creationflags=NOWINDOW)
        return "Hibernating..."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NetworkDiag
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NetworkDiag:
    @classmethod
    def ping(cls, host="8.8.8.8", count=4):
        try:
            r = subprocess.run(
                ["ping", "-n", str(count), host],
                capture_output=True, text=True, timeout=15,
                creationflags=NOWINDOW,
            )
            return r.stdout.strip() if r.returncode == 0 else f"Ping failed:\n{r.stdout}"
        except subprocess.TimeoutExpired:
            return f"Ping to {host} timed out."
        except Exception as e:
            return f"Ping error: {e}"

    @classmethod
    def get_ip_info(cls):
        lines = []
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            lines.append(f"  Local IP:  {s.getsockname()[0]}")
            s.close()
        except Exception:
            lines.append("  Local IP:  unavailable")
        try:
            r = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            for line in r.stdout.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    lines.append(f"  WiFi:      {line.split(':', 1)[1].strip()}")
                    break
        except Exception:
            pass
        lines.append(f"  Hostname:  {platform.node()}")
        return "\n".join(lines) if lines else "Network info unavailable."

    @classmethod
    def speedtest_lite(cls):
        try:
            start = time.time()
            urllib.request.urlopen("http://www.google.com/generate_204", timeout=5)
            return f"Latency to Google: {(time.time()-start)*1000:.0f}ms"
        except Exception as e:
            return f"Speed test failed: {e}"

    @classmethod
    def traceroute(cls, host="8.8.8.8"):
        try:
            r = subprocess.run(
                ["tracert", "-d", "-h", "15", host],
                capture_output=True, text=True, timeout=60,
                creationflags=NOWINDOW,
            )
            return r.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Traceroute timed out."
        except Exception as e:
            return f"Traceroute error: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SystemTriage
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SystemTriage:
    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_byte),
            ("BatteryFlag", ctypes.c_byte),
            ("BatteryLifePercent", ctypes.c_byte),
            ("SystemStatusFlag", ctypes.c_byte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    @classmethod
    def get_report(cls):
        lines = ["━━━ SOKOL System Report ━━━"]
        lines.append(f"  Host:    {platform.node()}")
        lines.append(f"  OS:      {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"  Arch:    {platform.machine()}")
        lines.append("")
        cpu = cls._cpu()
        if cpu is not None:
            lines.append(f"  CPU:     {cls._bar(cpu)}  {cpu:.0f}%")
        ram = cls._ram()
        if ram:
            lines.append(
                f"  RAM:     {cls._bar(ram['pct'])}  {ram['pct']:.0f}%  "
                f"({cls._fmb(ram['used'])} / {cls._fmb(ram['total'])})"
            )
        bat = cls._battery()
        if bat is None:
            lines.append("  Battery: No battery (desktop)")
        elif bat:
            st = "charging" if bat["charging"] else "discharging"
            lines.append(f"  Battery: {cls._bar(bat['percent'])}  {bat['percent']}% ({st})")
        for L in "CDEF":
            try:
                u = shutil.disk_usage(f"{L}:\\")
                pct = ((u.total - u.free) / u.total) * 100
                lines.append(
                    f"  Disk {L}:  {cls._bar(pct)}  {pct:.0f}%  "
                    f"({u.free/(1024**3):.1f} GB free / {u.total/(1024**3):.1f} GB)"
                )
            except Exception:
                continue
        net = cls._net()
        if net:
            lines.append(f"  Network: {net}")
        up = cls._uptime()
        if up:
            lines.append(f"  Uptime:  {up}")
        lines.append("━" * 38)
        return "\n".join(lines)

    @classmethod
    def _bar(cls, p, w=15):
        f = int(w * min(p, 100) / 100)
        return "#" * f + "-" * (w - f)

    @classmethod
    def _fmb(cls, mb):
        return f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"

    @classmethod
    def _cpu(cls):
        if HAS_PSUTIL:
            import psutil
            return psutil.cpu_percent(interval=0.5)
        try:
            r = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage", "/value"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            for line in r.stdout.strip().splitlines():
                if "=" in line:
                    return float(line.split("=")[1].strip())
        except Exception:
            pass
        return None

    @classmethod
    def _ram(cls):
        if HAS_PSUTIL:
            import psutil
            m = psutil.virtual_memory()
            return {"total": m.total/(1024**2), "used": m.used/(1024**2), "pct": m.percent}
        try:
            r = subprocess.run(
                ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"],
                capture_output=True, text=True, timeout=5,
                creationflags=NOWINDOW,
            )
            v = {}
            for line in r.stdout.strip().splitlines():
                if "=" in line:
                    k, val = line.split("=", 1)
                    v[k.strip()] = float(val.strip())
            tk = v.get("TotalVisibleMemorySize", 0)
            fk = v.get("FreePhysicalMemory", 0)
            if tk:
                tm, um = tk / 1024, (tk - fk) / 1024
                return {"total": tm, "used": um, "pct": (um / tm) * 100}
        except Exception:
            pass
        return None

    @classmethod
    def _battery(cls):
        if HAS_PSUTIL:
            import psutil
            b = psutil.sensors_battery()
            return {"percent": b.percent, "charging": b.power_plugged} if b else None
        try:
            s = cls.SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
                if s.BatteryLifePercent == 255:
                    return None
                return {"percent": s.BatteryLifePercent, "charging": s.ACLineStatus == 1}
        except Exception:
            pass
        return False

    @classmethod
    def _net(cls):
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return f"Connected (IP: {ip})"
        except Exception:
            return "Disconnected"

    @classmethod
    def _uptime(cls):
        try:
            ms = ctypes.windll.kernel32.GetTickCount64()
            s = ms // 1000
            d, h, m = s // 86400, (s % 86400) // 3600, (s % 3600) // 60
            parts = []
            if d:
                parts.append(f"{d}d")
            parts.append(f"{h}h {m}m")
            return " ".join(parts)
        except Exception:
            return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SystemQuickInfo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SystemQuickInfo:
    """Lightweight system snapshot for fast status checks."""

    @classmethod
    def get_status(cls):
        host = platform.node()
        cpu = SystemTriage._cpu()
        ram = SystemTriage._ram()
        uptime = SystemTriage._uptime()

        cpu_part = f"CPU {cpu:.0f}%" if cpu is not None else "CPU n/a"
        if ram:
            ram_part = f"RAM {ram['pct']:.0f}%"
        else:
            ram_part = "RAM n/a"
        up_part = f"Uptime {uptime}" if uptime else "Uptime n/a"
        return f"{host} | {cpu_part} | {ram_part} | {up_part}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WindowManager & ScreenManager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WindowManager:
    @classmethod
    def _kc(cls, *vks):
        u = ctypes.windll.user32
        for v in vks:
            u.keybd_event(v, 0, 0, 0)
        for v in reversed(vks):
            u.keybd_event(v, 0, 0x0002, 0)

    @classmethod
    def snap_left(cls):
        cls._kc(0x5B, 0x25); return "Window snapped left."
    @classmethod
    def snap_right(cls):
        cls._kc(0x5B, 0x27); return "Window snapped right."
    @classmethod
    def maximize(cls):
        cls._kc(0x5B, 0x26); return "Window maximized."
    @classmethod
    def minimize(cls):
        cls._kc(0x5B, 0x28); return "Window minimized."
    @classmethod
    def task_view(cls):
        cls._kc(0x5B, 0x09); return "Task View opened."
    @classmethod
    def alt_tab(cls):
        cls._kc(0x12, 0x09); return "Alt+Tab."
    @classmethod
    def close_window(cls):
        cls._kc(0x12, 0x73); return "Window closed (Alt+F4)."


class ScreenManager:
    @staticmethod
    def show_desktop():
        u = ctypes.windll.user32
        u.keybd_event(0x5B, 0, 0, 0)
        u.keybd_event(0x44, 0, 0, 0)
        u.keybd_event(0x44, 0, 0x0002, 0)
        u.keybd_event(0x5B, 0, 0x0002, 0)
        return "Desktop shown (Win+D)."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FileMachine & FileAgent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FileMachine:
    @classmethod
    def resolve_folder(cls, name):
        nl = name.lower().strip()
        if nl in FOLDER_ALIASES:
            return FOLDER_ALIASES[nl]
        for alias, path in FOLDER_ALIASES.items():
            if alias in nl or nl in alias:
                return path
        if os.path.isdir(name):
            return name
        exp = os.path.expanduser(name)
        if os.path.isdir(exp):
            return exp
        return None

    @classmethod
    def recent_files(cls, folder, count=10):
        entries = []
        try:
            for e in os.scandir(folder):
                if e.is_file(follow_symlinks=False):
                    try:
                        st = e.stat()
                        entries.append((st.st_mtime, e.name, st.st_size, e.path))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            return []
        entries.sort(key=lambda x: -x[0])
        result = []
        for mt, name, size, path in entries[:count]:
            dt = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
            if size >= 1024 * 1024:
                sz = f"{size/(1024*1024):.1f} MB"
            elif size >= 1024:
                sz = f"{size/1024:.1f} KB"
            else:
                sz = f"{size} B"
            result.append((dt, name, sz, path))
        return result

    @classmethod
    def format_report(cls, folder_name, files):
        if not files:
            return f"No files found in '{folder_name}'."
        lines = [f"━━━ Recent files in {folder_name} ━━━"]
        for i, (ts, name, size, _) in enumerate(files, 1):
            lines.append(f"  {i:2}. [{ts}]  {name}  ({size})")
        lines.append("━" * 35)
        return "\n".join(lines)


class FileAgent:
    """
    File operations with admin privilege awareness.
    v8.0: Added PermissionError handling with helpful user messages.
    """
    
    _FALLBACK_BASE = os.path.join(USER_HOME, "Documents", "Sokol_Files")

    @classmethod
    def _get_admin_warning(cls, path, operation="создания файла/папки"):
        """Generate helpful warning about missing admin rights."""
        from ..core import AdminHelper
        return AdminHelper.get_privilege_warning_text(operation)

    @classmethod
    def _ensure_fallback_dir(cls):
        """Ensure fallback directory exists for when admin rights are missing."""
        try:
            os.makedirs(cls._FALLBACK_BASE, exist_ok=True)
            return cls._FALLBACK_BASE
        except Exception:
            return USER_HOME

    @classmethod
    def create_folder(cls, path):
        """Create folder with proper error handling and admin warnings."""
        try:
            os.makedirs(path, exist_ok=True)
            return True, f"✅ Папка создана: {path}"
        except PermissionError:
            # No admin rights - suggest fallback or elevation
            warning = cls._get_admin_warning(path, "создания папки")
            fallback = cls._ensure_fallback_dir()
            alt_path = os.path.join(fallback, os.path.basename(path))
            try:
                os.makedirs(alt_path, exist_ok=True)
                return True, (
                    f"✅ Папка создана в пользовательской директории: {alt_path}\n"
                    f"⚠️ Не удалось создать в {path} — нет прав.\n{warning}"
                )
            except Exception as e2:
                return False, f"❌ Ошибка создания папки:\n{warning}\nДетали: {e2}"
        except Exception as e:
            return False, f"❌ Ошибка создания папки: {e}"

    @classmethod
    def create_file(cls, path, content=""):
        """Create file with proper error handling and admin warnings."""
        # Expand user paths like ~/filename.txt
        path = os.path.expanduser(path)
        
        # If just a filename without directory, put in fallback dir
        if not os.path.dirname(path):
            path = os.path.join(cls._ensure_fallback_dir(), path)
        
        try:
            # Ensure parent directory exists
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"✅ Файл создан: {path}"
        except PermissionError:
            # No admin rights - try fallback location
            warning = cls._get_admin_warning(path, "создания файла")
            fallback = cls._ensure_fallback_dir()
            alt_name = os.path.basename(path) or "file.txt"
            alt_path = os.path.join(fallback, alt_name)
            try:
                with open(alt_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, (
                    f"✅ Файл создан в пользовательской директории: {alt_path}\n"
                    f"⚠️ Не удалось создать в {path} — нет прав администратора.\n"
                    f"{warning}"
                )
            except Exception as e2:
                return False, f"❌ Ошибка создания файла:\n{warning}\nДетали: {e2}"
        except Exception as e:
            return False, f"❌ Ошибка создания файла: {e}"

    @classmethod
    def open_in_explorer(cls, path):
        """Open file or folder in Explorer."""
        try:
            if os.path.isdir(path):
                os.startfile(path)
                return True, f"Открыта папка: {path}"
            elif os.path.isfile(path):
                subprocess.Popen(
                    ["explorer", "/select,", path], creationflags=NOWINDOW
                )
                return True, f"Файл выделен в проводнике: {path}"
            else:
                return False, f"Путь не существует: {path}"
        except PermissionError:
            warning = cls._get_admin_warning(path, "открытия в проводнике")
            return False, f"❌ Нет доступа к пути:\n{warning}"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    @classmethod
    def delete_file(cls, path):
        """Delete file with admin warnings."""
        try:
            if os.path.exists(path):
                os.remove(path)
                return True, f"✅ Файл удалён: {path}"
            return False, f"Файл не найден: {path}"
        except PermissionError:
            warning = cls._get_admin_warning(path, "удаления файла")
            return False, f"❌ Нет прав на удаление:\n{warning}"
        except Exception as e:
            return False, f"❌ Ошибка удаления: {e}"

    @classmethod
    def read_file(cls, path):
        """Read file contents with admin warnings."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return True, f.read()
        except PermissionError:
            warning = cls._get_admin_warning(path, "чтения файла")
            return False, f"❌ Нет прав на чтение:\n{warning}"
        except Exception as e:
            return False, f"❌ Ошибка чтения: {e}"

    @classmethod
    def append_to_file(cls, path, content):
        """Append content to file with admin warnings."""
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return True, f"✅ Добавлено в файл: {path}"
        except PermissionError:
            warning = cls._get_admin_warning(path, "записи в файл")
            return False, f"❌ Нет прав на запись:\n{warning}"
        except Exception as e:
            return False, f"❌ Ошибка записи: {e}"


class ContentSearch:
    """
    Fast search inside files with file+line output.
    Uses ripgrep when available, falls back to Python scan.
    """

    @classmethod
    def search(cls, query, root=None, max_results=40):
        query = (query or "").strip()
        if not query:
            return False, "Пустой запрос."
        root = root or USER_HOME

        # Fast path: ripgrep
        try:
            cmd = ["rg", "-n", "--hidden", "--smart-case", "--max-count", str(max_results), query, root]
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=25, creationflags=NOWINDOW
            )
            out = (r.stdout or "").strip()
            if out:
                lines = out.splitlines()[:max_results]
                return True, cls._format_results(query, lines)
        except Exception:
            pass

        # Fallback: Python streaming scan
        results = []
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "windows", "system32", "winsxs", ".cursor", ".idea",
        }
        try:
            ql = query.lower()
            for dp, dn, fn in os.walk(root):
                INTERRUPT.check()
                dn[:] = [d for d in dn if d.lower() not in skip_dirs]
                for name in fn:
                    INTERRUPT.check()
                    path = os.path.join(dp, name)
                    try:
                        if os.path.getsize(path) > 2 * 1024 * 1024:
                            continue
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if ql in line.lower():
                                    rel = os.path.relpath(path, root)
                                    results.append(f"{rel}:{i}:{line.strip()}")
                                    if len(results) >= max_results:
                                        return True, cls._format_results(query, results)
                    except (PermissionError, OSError):
                        continue
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"Поиск не удался: {e}"

        if not results:
            return True, f"Ничего не найдено по запросу: {query}"
        return True, cls._format_results(query, results)

    @classmethod
    def _format_results(cls, query, rows):
        lines = [f"━━━ Найдено по запросу: {query} ━━━"]
        for i, row in enumerate(rows[:40], 1):
            lines.append(f"  {i:2}. {row[:260]}")
        lines.append("━" * 40)
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WindowEnumerator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WindowEnumerator:
    @classmethod
    def list_windows(cls):
        windows = []
        def cb(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    t = buf.value.strip()
                    if t:
                        windows.append({"hwnd": hwnd, "title": t})
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(cb), 0)
        return windows

    @classmethod
    def format_report(cls):
        w = cls.list_windows()
        if not w:
            return "No visible windows found."
        lines = ["━━━ Open Windows ━━━"]
        for i, win in enumerate(w, 1):
            lines.append(f"  {i:2}. {win['title'][:80]}")
        lines.append(f"━━━ Total: {len(w)} windows ━━━")
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ServiceManager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ServiceManager:
    @classmethod
    def list_services(cls, filter_status=None):
        try:
            r = subprocess.run(
                ["sc", "query", "type=", "service", "state=", "all"],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            services, cur = [], {}
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("SERVICE_NAME:"):
                    if cur:
                        services.append(cur)
                    cur = {"name": line.split(":", 1)[1].strip()}
                elif line.startswith("DISPLAY_NAME:"):
                    cur["display"] = line.split(":", 1)[1].strip()
                elif line.startswith("STATE"):
                    cur["state"] = "RUNNING" if "RUNNING" in line else "STOPPED"
            if cur:
                services.append(cur)
            if filter_status:
                services = [
                    s for s in services
                    if s.get("state") == filter_status.upper()
                ]
            return services
        except Exception:
            return []

    @classmethod
    def start_service(cls, name):
        try:
            r = subprocess.run(
                ["net", "start", name],
                capture_output=True, text=True, timeout=15,
                creationflags=NOWINDOW,
            )
            return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def stop_service(cls, name):
        try:
            r = subprocess.run(
                ["net", "stop", name],
                capture_output=True, text=True, timeout=15,
                creationflags=NOWINDOW,
            )
            return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def restart_service(cls, name):
        cls.stop_service(name)
        time.sleep(2)
        return cls.start_service(name)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WiFiManager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WiFiManager:
    @classmethod
    def get_profiles(cls):
        try:
            r = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            profiles = []
            for line in r.stdout.splitlines():
                if ":" in line and ("Profile" in line or "Все" in line):
                    name = line.split(":", 1)[1].strip()
                    if name:
                        profiles.append(name)
            return profiles
        except Exception:
            return []

    @classmethod
    def get_password(cls, profile):
        try:
            r = subprocess.run(
                ["netsh", "wlan", "show", "profile", profile, "key=clear"],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            for line in r.stdout.splitlines():
                if "Key Content" in line or "ключа" in line:
                    return line.split(":", 1)[1].strip()
            return "(no password)"
        except Exception as e:
            return f"Error: {e}"

    @classmethod
    def get_all_passwords(cls):
        profiles = cls.get_profiles()
        if not profiles:
            return "No WiFi profiles found."
        lines = ["━━━ Saved WiFi Passwords ━━━"]
        for p in profiles:
            lines.append(f"  {p}: {cls.get_password(p)}")
        lines.append("━" * 35)
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DiskAnalyzer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DiskAnalyzer:
    @classmethod
    def find_large_files(cls, directory=None, top=20, min_mb=50):
        directory = directory or USER_HOME
        large = []
        min_bytes = min_mb * 1024 * 1024
        skip = {"$recycle.bin", "system volume information", "windows", "winsxs"}
        try:
            for dp, dn, fn in os.walk(directory):
                INTERRUPT.check()
                dn[:] = [d for d in dn if d.lower() not in skip]
                for f in fn:
                    full = os.path.join(dp, f)
                    try:
                        sz = os.path.getsize(full)
                        if sz >= min_bytes:
                            large.append((sz, full))
                    except (PermissionError, OSError):
                        continue
        except InterruptedError:
            raise
        except (PermissionError, OSError):
            pass
        large.sort(key=lambda x: -x[0])
        return large[:top]

    @classmethod
    def format_report(cls, files):
        if not files:
            return "No large files found."
        lines = ["━━━ Largest Files ━━━"]
        for i, (sz, p) in enumerate(files, 1):
            s = f"{sz/(1024**3):.2f} GB" if sz >= 1024**3 else f"{sz/(1024**2):.1f} MB"
            lines.append(f"  {i:2}. [{s}]  {p}")
        lines.append("━" * 35)
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# StartupManager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class StartupManager:
    @classmethod
    def list_startup(cls):
        items = []
        try:
            r = subprocess.run(
                ["wmic", "startup", "get", "name,command", "/format:csv"],
                capture_output=True, text=True, timeout=10,
                creationflags=NOWINDOW,
            )
            for line in r.stdout.strip().splitlines()[1:]:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    name = parts[1].strip()
                    if name:
                        items.append({"name": name, "command": parts[2].strip()})
        except Exception:
            pass
        return items

    @classmethod
    def format_report(cls):
        items = cls.list_startup()
        if not items:
            return "No startup items found."
        lines = ["━━━ Startup Programs ━━━"]
        for i, it in enumerate(items, 1):
            lines.append(f"  {i}. {it['name']}")
            lines.append(f"     {it['command'][:80]}")
        lines.append("━" * 35)
        return "\n".join(lines)
