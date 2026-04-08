# -*- coding: utf-8 -*-
"""
SOKOL v7 — GUI Automation & Vision
GUIAutomation, VisionLite (EasyOCR), ScreenCapture, BulkFileOps
"""
import os
import re
import time
import shutil
import zipfile
import subprocess
import ctypes
import json
import base64
from functools import wraps
from datetime import datetime
from .config import (
    NOWINDOW, HAS_PYAUTOGUI, HAS_EASYOCR, SCREENSHOTS_DIR,
    HAS_PYGETWINDOW, HAS_PYWIN32
)
from .core import INTERRUPT

def retry_action(max_retries=3, delay=1.0, backoff=2.0):
    """Decorator for retrying actions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            # Log failure with screenshot if it's a GUI action
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = os.path.join(SCREENSHOTS_DIR, f"error_log_{ts}.json")
                os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
                
                error_data = {
                    "timestamp": ts,
                    "function": func.__name__,
                    "args": str(args[1:]) if len(args) > 1 else str(args),
                    "exception": str(last_exception),
                    "attempt": max_retries
                }
                
                # Take screenshot
                if HAS_PYAUTOGUI:
                    import pyautogui
                    from io import BytesIO
                    screenshot = pyautogui.screenshot()
                    buffered = BytesIO()
                    screenshot.save(buffered, format="PNG")
                    error_data["screenshot_base64"] = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(error_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
                
            raise last_exception
        return wrapper
    return decorator

class GUIAutomation:
    """Mouse/keyboard control via PyAutoGUI."""

    @classmethod
    @retry_action(max_retries=3)
    def focus_window(cls, title_part):
        """
        Force focus on window containing title_part with verification.
        v7.9: Strictly enforces visibility and bypasses Windows focus locks.
        """
        target_hwnd = None
        
        if HAS_PYWIN32:
            import win32gui
            import win32con
            def callback(hwnd, extra):
                nonlocal target_hwnd
                # 1. Check title
                title = win32gui.GetWindowText(hwnd)
                if title_part.lower() not in title.lower():
                    return True
                
                # 2. STRICT VISIBILITY CHECK (v7.9)
                # Ignore invisible windows (tray icons, push notifications, etc.)
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                # 3. EMPTY RECT CHECK (v7.9)
                rect = win32gui.GetWindowRect(hwnd)
                if rect[2] - rect[0] <= 0 or rect[3] - rect[1] <= 0:
                    return True
                
                target_hwnd = hwnd
                return False # Found it, stop enumeration
            
            win32gui.EnumWindows(callback, None)

        if not target_hwnd and HAS_PYGETWINDOW:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title_part)
            for w in wins:
                if win32gui.IsWindowVisible(w._hWnd):
                    target_hwnd = w._hWnd
                    break

        if target_hwnd:
            import win32gui
            import win32con
            import pyautogui
            
            # WAKE UP INPUT QUEUE (v7.9 Alt-key trick)
            # This bypasses Windows restriction on SetForegroundWindow from background apps.
            try:
                pyautogui.press('alt')
            except Exception:
                pass
            
            if win32gui.IsIconic(target_hwnd):
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            
            # Bring to front
            win32gui.SetForegroundWindow(target_hwnd)
            
            # Verify foreground (v7.9: more lenient for slow apps)
            timeout = time.time() + 3.0
            while time.time() < timeout:
                if win32gui.GetForegroundWindow() == target_hwnd:
                    time.sleep(0.6) # Wait for UI rendering
                    return True, f"Focused window HWND: {target_hwnd}"
                # Sometimes it's a child window that gets focus, check if parent is target
                fg_hwnd = win32gui.GetForegroundWindow()
                if win32gui.GetParent(fg_hwnd) == target_hwnd:
                    time.sleep(0.6)
                    return True, f"Focused child of HWND: {target_hwnd}"
                time.sleep(0.2)
            
            # Even if verification failed, we tried to focus it.
            return True, "Focused (verification timed out but window brought to front)"
        
        return False, f"Visible window with title '{title_part}' not found."

    @classmethod
    def get_keyboard_layout(cls):
        """Get current keyboard layout ID."""
        if not HAS_PYWIN32:
            return None
        try:
            import win32gui
            import win32process
            import win32api
            hwnd = win32gui.GetForegroundWindow()
            thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
            layout_id = win32api.GetKeyboardLayout(thread_id)
            return layout_id & 0xFFFF
        except Exception:
            return None

    @classmethod
    def hotkey_search(cls):
        """Ctrl+F — поиск внутри окна (блокнот, браузер и т.д.)."""
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"

        import pyautogui
        try:
            pyautogui.keyDown('ctrl')
            time.sleep(0.05)
            pyautogui.press('f')
            time.sleep(0.05)
            pyautogui.keyUp('ctrl')

            time.sleep(0.3)

            pyautogui.keyDown('ctrl')
            pyautogui.press('a')
            pyautogui.keyUp('ctrl')
            time.sleep(0.1)
            pyautogui.press('backspace')

            time.sleep(0.2)
            return True, "Search hotkey sent and field sanitized"
        except Exception as e:
            return False, f"Search hotkey failed: {e}"

    @classmethod
    def ensure_english_layout(cls):
        """
        Forces the foreground window to English layout.
        v7.9.19: Enhanced layout switching via WinAPI.
        """
        if not HAS_PYWIN32:
            return False
        try:
            import win32gui
            import win32api
            import win32con
            
            hwnd = win32gui.GetForegroundWindow()
            # English (United States) layout string
            layout_en = "00000409"
            # Load and activate layout
            h_layout = win32api.LoadKeyboardLayout(layout_en, 1) # KLF_ACTIVATE = 1
            # Post message to window to change its input language
            win32api.PostMessage(hwnd, 0x0050, 1, h_layout) # WM_INPUTLANGCHANGEREQUEST = 0x0050
            time.sleep(0.3)
            return True
        except Exception:
            return False

    @classmethod
    def hotkey_telegram_jump_chat(cls):
        """
        Telegram/AyuGram Desktop: Global search for contact.
        v7.9.17: Using low-level win32api keybd_event for maximum bypass.
        """
        try:
            import win32api
            import win32con
            import time

            # 1. FORCE ENGLISH LAYOUT
            cls.ensure_english_layout()
            time.sleep(0.3)

            # 2. LOW-LEVEL KEY SEQUENCE (Bypasses many high-level filters)
            # VK_CONTROL = 0x11, VK_F = 0x46
            
            # Press Ctrl
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.15)
            
            # Press F
            win32api.keybd_event(0x46, 0, 0, 0)
            time.sleep(0.15)
            
            # Release F
            win32api.keybd_event(0x46, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.15)
            
            # Release Ctrl
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            # 3. Wait for UI response
            time.sleep(1.0)

            # 4. Aggressive clear (Ctrl+A -> Backspace)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(0x41, 0, 0, 0) # VK_A = 0x41
            time.sleep(0.1)
            win32api.keybd_event(0x41, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            time.sleep(0.2)
            win32api.keybd_event(win32con.VK_BACK, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_BACK, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            time.sleep(0.3)
            return True, "Telegram Search focused (Low-level WinAPI)"
        except Exception as e:
            return False, f"Telegram jump-chat hotkey failed: {e}"

    @classmethod
    def hotkey_ctrl_k(cls):
        """Алиас для поиска чата в Telegram (Ctrl+K)."""
        return cls.hotkey_telegram_jump_chat()

    @classmethod
    def hibernate(cls):
        try:
            ctypes.windll.PowrProf.SetSuspendState(1, 1, 0)
            return True, "Hibernating PC."
        except Exception as e:
            return False, f"Hibernate failed: {e}"

    @classmethod
    def empty_recycle_bin(cls):
        """Empty the Windows Recycle Bin."""
        try:
            # SHEmptyRecycleBinW (HWND, root, flags)
            # flags: 1 = SHERB_NOCONFIRMATION, 2 = SHERB_NOPROGRESSUI, 4 = SHERB_NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(0, None, 1 | 2 | 4)
            return True, "Recycle Bin emptied."
        except Exception as e:
            return False, f"Failed to empty Recycle Bin: {e}"

    @classmethod
    def open_disc_drive(cls):
        """Open the optical disc drive tray."""
        try:
            ctypes.windll.winmm.mciSendStringW("set cdaudio door open", None, 0, 0)
            return True, "Disc drive opened."
        except Exception as e:
            return False, f"Failed to open disc drive: {e}"

    @classmethod
    def close_disc_drive(cls):
        """Close the optical disc drive tray."""
        try:
            ctypes.windll.winmm.mciSendStringW("set cdaudio door closed", None, 0, 0)
            return True, "Disc drive closed."
        except Exception as e:
            return False, f"Failed to close disc drive: {e}"

    @classmethod
    def type_dictation(cls, text):
        """Type text into the currently focused window using dictation mode."""
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            # Small delay to let user switch if needed, though this is usually immediate
            time.sleep(0.5)
            # Use type_unicode if it has non-ascii, otherwise type_text
            if any(ord(c) > 127 for c in text):
                return cls.type_unicode(text)
            else:
                return cls.type_text(text)
        except Exception as e:
            return False, f"Dictation failed: {e}"

    @classmethod
    def available(cls):
        return HAS_PYAUTOGUI
    @classmethod
    def click(cls, x, y, button="left", clicks=1):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed. Run: pip install pyautogui"
        try:
            import pyautogui
            pyautogui.click(x, y, button=button, clicks=clicks)
            return True, f"Clicked at ({x}, {y}) [{button}]"
        except Exception as e:
            return False, f"Click failed: {e}"
    @classmethod
    def double_click(cls, x, y):
        return cls.click(x, y, clicks=2)
    @classmethod
    def right_click(cls, x, y):
        return cls.click(x, y, button="right")
    @classmethod
    @retry_action(max_retries=2)
    def type_text(cls, text, interval=0.03):
        """Type text with jitter to bypass basic anti-bot or buffer issues."""
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            old_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            
            import random
            for char in text:
                # Add jitter to interval
                jitter = random.uniform(-0.01, 0.01)
                actual_interval = max(0.01, interval + jitter)
                pyautogui.typewrite(char)
                time.sleep(actual_interval)
            
            pyautogui.FAILSAFE = old_failsafe
            return True, f"Typed with jitter: {text[:50]}{'...' if len(text) > 50 else ''}"
        except Exception as e:
            try: pyautogui.FAILSAFE = True # Restore on error
            except: pass
            return False, f"Type failed: {e}"
    @classmethod
    def low_level_press(cls, vk_code):
        """Press a key using low-level WinAPI keybd_event."""
        try:
            import win32api
            import win32con
            win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

    @classmethod
    def type_unicode(cls, text):
        """
        Type unicode text (Cyrillic etc.) via clipboard paste.
        v7.9.19: Using low-level WinAPI for Ctrl+V sequence for maximum bypass.
        v8.0: Added fallback without pywin32 dependency and pyautogui final fallback.
        """
        text = str(text)
        
        # METHOD 1: Try pywin32 method first (most reliable)
        try:
            import win32clipboard
            import win32api
            import win32con
            
            # 1. Set Clipboard with retries
            for attempt in range(5):  # Increased from 3 to 5
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    break
                except Exception:
                    time.sleep(0.2)
                    if attempt == 4:  # Last attempt
                        raise
                    try:
                        win32clipboard.CloseClipboard()  # Ensure cleanup
                    except:
                        pass
            
            time.sleep(0.3)
            
            # 2. LOW-LEVEL CTRL+V with proper timing
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(0x56, 0, 0, 0)  # 'V'
            time.sleep(0.05)
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            time.sleep(0.2)
            return True, f"Typed (WinAPI): {text[:50]}"
            
        except ImportError:
            pass  # pywin32 not available
        except Exception as e:
            print(f"pywin32 method failed: {e}")
            try:
                import win32clipboard
                win32clipboard.CloseClipboard()  # Cleanup
            except:
                pass
        
        # METHOD 2: Pure ctypes with multiple retries
        for attempt in range(3):
            try:
                CF_UNICODETEXT = 13
                GHND = 0x0042
                
                data = text.encode('utf-16-le')
                size = len(data) + 2
                
                # Open clipboard
                if not ctypes.windll.user32.OpenClipboard(0):
                    if attempt < 2:
                        time.sleep(0.3)
                        continue
                    return False, "Failed to open clipboard"
                
                try:
                    ctypes.windll.user32.EmptyClipboard()
                    
                    # Allocate global memory
                    handle = ctypes.windll.kernel32.GlobalAlloc(GHND, size)
                    if not handle:
                        if attempt < 2:
                            time.sleep(0.3)
                            continue
                        return False, "Failed to allocate memory"
                    
                    ptr = ctypes.windll.kernel32.GlobalLock(handle)
                    if not ptr:
                        ctypes.windll.kernel32.GlobalFree(handle)
                        if attempt < 2:
                            time.sleep(0.3)
                            continue
                        return False, "Failed to lock memory"
                    
                    ctypes.memmove(ptr, data, len(data))
                    ctypes.windll.kernel32.GlobalUnlock(handle)
                    
                    # Set clipboard data
                    ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)
                finally:
                    ctypes.windll.user32.CloseClipboard()
                
                time.sleep(0.3)
                
                # Simulate Ctrl+V using ctypes
                VK_CONTROL = 0x11
                VK_V = 0x56
                
                ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_V, 0, 2, 0)  # KEYUP
                ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)  # KEYUP
                
                time.sleep(0.2)
                return True, f"Typed (ctypes): {text[:50]}"
                
            except Exception as e:
                print(f"ctypes method attempt {attempt+1} failed: {e}")
                try:
                    ctypes.windll.user32.CloseClipboard()
                except:
                    pass
                if attempt < 2:
                    time.sleep(0.3)
                    continue
        
        # METHOD 3: Final fallback - pyautogui character-by-character
        try:
            import pyautogui
            # Type with small delay between characters
            pyautogui.write(text, interval=0.01)
            return True, f"Typed (pyautogui): {text[:50]}"
        except Exception as e:
            return False, f"All typing methods failed: {e}"
            
            # Send Ctrl+V using keybd_event
            VK_CONTROL = 0x11
            VK_V = 0x56
            KEYEVENTF_KEYUP = 0x0002
            
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            
            time.sleep(0.2)
            return True, f"Typed (unicode via ctypes): {text[:50]}"
        except Exception as e:
            return False, f"Unicode type failed (pywin32 not installed, ctypes fallback failed): {e}"
    @classmethod
    def hotkey(cls, *keys):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True, f"Hotkey: {'+'.join(keys)}"
        except Exception as e:
            return False, f"Hotkey failed: {e}"
    @classmethod
    def press(cls, key, presses=1, interval=0.05):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            pyautogui.press(key, presses=presses, interval=interval)
            return True, f"Pressed: {key} x{presses}"
        except Exception as e:
            return False, f"Press failed: {e}"
    @classmethod
    def move_to(cls, x, y, duration=0.3):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            return True, f"Mouse moved to ({x}, {y})"
        except Exception as e:
            return False, f"Move failed: {e}"
    @classmethod
    def drag_to(cls, x, y, duration=0.5, button="left"):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            pyautogui.dragTo(x, y, duration=duration, button=button)
            return True, f"Dragged to ({x}, {y})"
        except Exception as e:
            return False, f"Drag failed: {e}"
    @classmethod
    def scroll(cls, clicks, x=None, y=None):
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed"
        try:
            import pyautogui
            pyautogui.scroll(clicks, x=x, y=y)
            direction = "up" if clicks > 0 else "down"
            return True, f"Scrolled {direction} ({abs(clicks)} clicks)"
        except Exception as e:
            return False, f"Scroll failed: {e}"
    @classmethod
    def get_screen_size(cls):
        if not HAS_PYAUTOGUI:
            return None, None
        import pyautogui
        return pyautogui.size()
    @classmethod
    def get_mouse_position(cls):
        if not HAS_PYAUTOGUI:
            return None, None
        import pyautogui
        return pyautogui.position()
class ScreenCapture:
    """Take screenshots (full or region)."""
    @classmethod
    def take(cls, region=None):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(SCREENSHOTS_DIR, f"sokol_{ts}.png")
        if HAS_PYAUTOGUI:
            try:
                import pyautogui
                img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
                img.save(filepath)
                return True, f"Screenshot saved: {filepath}", filepath
            except Exception as e:
                return False, f"Screenshot failed: {e}", None
        else:
            try:
                import ctypes
                ctypes.windll.user32.keybd_event(0x2C, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x2C, 0, 0x0002, 0)
                time.sleep(0.5)
                return True, "Screenshot copied to clipboard (Print Screen).", None
            except Exception as e:
                return False, f"Screenshot failed: {e}", None
    @classmethod
    def take_region(cls, x, y, w, h):
        return cls.take(region=(x, y, w, h))
class VisionLite:
    """
    Screen OCR and text-based click automation.
    Uses EasyOCR to recognize text on screen, then clicks on found coordinates.
    v8.0: Added minimize/restore support for reading screen behind SOKOL window.
    """
    _reader = None
    _sokol_hwnd = None
    
    @classmethod
    def _get_sokol_hwnd(cls):
        """Find SOKOL window handle."""
        if cls._sokol_hwnd is not None:
            return cls._sokol_hwnd
            
        def enum_cb(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.lower()
                    if "sokol" in title and ("elite" in title or "v8" in title or "v7" in title):
                        cls._sokol_hwnd = hwnd
                        return False
            return True
            
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return cls._sokol_hwnd

    @classmethod
    def _get_reader(cls):
        """Lazy-init EasyOCR reader (ru+en). Used by ocr_screen, VisionAgent, messenger OCR."""
        if not HAS_EASYOCR:
            return None
        if cls._reader is not None:
            return cls._reader
        try:
            import easyocr

            env_gpu = os.environ.get("SOKOL_EASYOCR_GPU", "").strip().lower()
            if env_gpu in ("0", "false", "no", "off"):
                want_gpu = False
            elif env_gpu in ("1", "true", "yes", "on"):
                want_gpu = True
            else:
                want_gpu = False
                try:
                    import torch

                    want_gpu = bool(torch.cuda.is_available())
                except Exception:
                    want_gpu = False
            cls._reader = easyocr.Reader(["ru", "en"], gpu=want_gpu)
        except Exception:
            cls._reader = None
        return cls._reader

    @classmethod
    def minimize_sokol(cls):
        """Minimize SOKOL window before OCR."""
        hwnd = cls._get_sokol_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            time.sleep(0.5)  # Wait for minimize animation
            return True
        return False
    
    @classmethod  
    def restore_sokol(cls):
        """Restore SOKOL window after OCR."""
        hwnd = cls._get_sokol_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
        return False
    
    @classmethod
    def ocr_screen(cls, region=None, minimize_first=False):
        """
        Take screenshot and run OCR. Returns list of {text, bbox, confidence}.
        
        Args:
            region: Optional (x, y, w, h) tuple for region capture
            minimize_first: If True, minimize SOKOL window before OCR (v8.0)
        """
        if not HAS_EASYOCR:
            return False, "EasyOCR not installed. Run: pip install easyocr", []
        if not HAS_PYAUTOGUI:
            return False, "pyautogui not installed for screenshots.", []
        
        # Minimize SOKOL if requested
        if minimize_first:
            cls.minimize_sokol()
            
        reader = cls._get_reader()
        if not reader:
            if minimize_first:
                cls.restore_sokol()
            return False, "Failed to init OCR reader.", []
        try:
            import pyautogui
            import numpy as np
            
            # Small delay to ensure window is minimized
            if minimize_first:
                time.sleep(0.3)
                
            img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            img_np = np.array(img)
            results = reader.readtext(img_np)
            parsed = []
            for bbox, text, conf in results:
                # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                cx = int((min(xs) + max(xs)) / 2)
                cy = int((min(ys) + max(ys)) / 2)
                parsed.append({
                    "text": text,
                    "x": cx, "y": cy,
                    "confidence": round(conf, 2),
                    "bbox": bbox,
                })
            
            # Restore SOKOL window
            if minimize_first:
                cls.restore_sokol()
                
            return True, f"OCR found {len(parsed)} text regions.", parsed
        except Exception as e:
            if minimize_first:
                cls.restore_sokol()
            return False, f"OCR failed: {e}", []
    
    @classmethod
    def ocr_screen_with_minimize(cls, region=None):
        """Convenience method: OCR with SOKOL minimized."""
        return cls.ocr_screen(region=region, minimize_first=True)
    @classmethod
    def find_text_on_screen(cls, target_text, region=None):
        """Find text on screen and return its coordinates."""
        ok, msg, results = cls.ocr_screen(region)
        if not ok:
            return False, msg, None
        target_lower = target_text.lower().strip()
        best_match = None
        best_ratio = 0
        for item in results:
            text_lower = item["text"].lower().strip()
            if target_lower in text_lower or text_lower in target_lower:
                return True, f"Found '{item['text']}' at ({item['x']}, {item['y']})", item
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, target_lower, text_lower).ratio()
            if ratio > best_ratio and ratio > 0.6:
                best_ratio = ratio
                best_match = item
        if best_match:
            return True, f"Best match: '{best_match['text']}' at ({best_match['x']}, {best_match['y']})", best_match
        return False, f"Text '{target_text}' not found on screen.", None
    @classmethod
    def click_text(cls, target_text, region=None):
        """Find text on screen and click on it."""
        ok, msg, item = cls.find_text_on_screen(target_text, region)
        if not ok or not item:
            return False, msg
        return GUIAutomation.click(item["x"], item["y"])
    @classmethod
    def ocr_report(cls, region=None):
        """Get formatted OCR report."""
        ok, msg, results = cls.ocr_screen(region)
        if not ok:
            return msg
        if not results:
            return "No text found on screen."
        lines = ["━━━ Screen OCR Results ━━━"]
        for i, item in enumerate(results[:30], 1):
            lines.append(
                f"  {i:2}. [{item['confidence']:.0%}] \"{item['text']}\" "
                f"at ({item['x']}, {item['y']})"
            )
        if len(results) > 30:
            lines.append(f"  ... and {len(results) - 30} more")
        lines.append("━" * 35)
        return "\n".join(lines)
class BulkFileOps:
    """Mass file operations: rename, delete by extension, ZIP."""
    @classmethod
    def rename_batch(cls, folder, pattern, replacement):
        """Rename files matching pattern in folder."""
        if not os.path.isdir(folder):
            return False, f"Folder not found: {folder}"
        renamed = []
        try:
            for fname in os.listdir(folder):
                full = os.path.join(folder, fname)
                if not os.path.isfile(full):
                    continue
                new_name = re.sub(pattern, replacement, fname)
                if new_name != fname:
                    new_full = os.path.join(folder, new_name)
                    os.rename(full, new_full)
                    renamed.append(f"{fname} -> {new_name}")
                    INTERRUPT.check()
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"Rename error: {e}"
        if renamed:
            return True, f"Renamed {len(renamed)} files:\n" + "\n".join(renamed[:20])
        return True, "No files matched the pattern."
    @classmethod
    def delete_by_extension(cls, folder, extension):
        """Delete all files with given extension in folder."""
        if not os.path.isdir(folder):
            return False, f"Folder not found: {folder}"
        ext = extension if extension.startswith(".") else f".{extension}"
        deleted = []
        try:
            for fname in os.listdir(folder):
                if fname.lower().endswith(ext.lower()):
                    full = os.path.join(folder, fname)
                    if os.path.isfile(full):
                        os.remove(full)
                        deleted.append(fname)
                        INTERRUPT.check()
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"Delete error: {e}"
        if deleted:
            return True, f"Deleted {len(deleted)} {ext} files."
        return True, f"No {ext} files found."
    @classmethod
    def zip_folder(cls, folder, output_path=None):
        """Compress folder to ZIP."""
        if not os.path.isdir(folder):
            return False, f"Folder not found: {folder}"
        if not output_path:
            output_path = folder.rstrip(os.sep) + ".zip"
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for dirpath, dirnames, filenames in os.walk(folder):
                    INTERRUPT.check()
                    for fname in filenames:
                        full = os.path.join(dirpath, fname)
                        arcname = os.path.relpath(full, folder)
                        zf.write(full, arcname)
            size = os.path.getsize(output_path)
            sz = f"{size / (1024*1024):.1f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB"
            return True, f"ZIP created: {output_path} ({sz})"
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"ZIP error: {e}"
    @classmethod
    def unzip(cls, zip_path, output_dir=None):
        """Extract ZIP archive."""
        if not os.path.isfile(zip_path):
            return False, f"File not found: {zip_path}"
        if not output_dir:
            output_dir = os.path.splitext(zip_path)[0]
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(output_dir)
            return True, f"Extracted to: {output_dir}"
        except Exception as e:
            return False, f"Unzip error: {e}"
    @classmethod
    def move_by_extension(cls, src_folder, dest_folder, extension):
        """Move files with given extension to another folder."""
        if not os.path.isdir(src_folder):
            return False, f"Source not found: {src_folder}"
        os.makedirs(dest_folder, exist_ok=True)
        ext = extension if extension.startswith(".") else f".{extension}"
        moved = 0
        try:
            for fname in os.listdir(src_folder):
                if fname.lower().endswith(ext.lower()):
                    src = os.path.join(src_folder, fname)
                    dst = os.path.join(dest_folder, fname)
                    if os.path.isfile(src):
                        shutil.move(src, dst)
                        moved += 1
                        INTERRUPT.check()
        except InterruptedError:
            raise
        except Exception as e:
            return False, f"Move error: {e}"
        return True, f"Moved {moved} {ext} files to {dest_folder}"
