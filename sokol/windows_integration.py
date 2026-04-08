# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Windows System Integration
Toast notifications, system tray, startup integration
"""
import os
import sys
import threading
from typing import Callable, Optional

try:
    import win32gui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False

class WindowsIntegration:
    """
    Windows-specific integrations for SOKOL
    - Toast notifications
    - System tray (future)
    - Startup registration
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
        self.initialized = True
        self.toast_notifier = None
        if TOAST_AVAILABLE:
            try:
                self.toast_notifier = ToastNotifier()
            except:
                pass
    
    def show_notification(self, title: str, message: str, duration: int = 5,
                          callback: Optional[Callable] = None):
        """
        Show Windows toast notification
        
        Args:
            title: Notification title
            message: Notification body
            duration: Duration in seconds
            callback: Function to call on click (if supported)
        """
        if self.toast_notifier:
            try:
                self.toast_notifier.show_toast(
                    title,
                    message,
                    duration=duration,
                    threaded=True
                )
                return True
            except Exception as e:
                print(f"Toast notification failed: {e}")
        
        # Fallback: try Windows API directly
        if WIN32_AVAILABLE:
            try:
                self._show_native_notification(title, message)
                return True
            except:
                pass
        
        return False
    
    def _show_native_notification(self, title: str, message: str):
        """Show notification using Windows API"""
        # Create message box that auto-closes
        # Using MB_OK with timeout would need custom implementation
        # For now, just log
        print(f"[NOTIFICATION] {title}: {message}")
    
    def register_startup(self, enable: bool = True):
        """
        Register/unregister SOKOL to run at Windows startup
        
        Args:
            enable: True to add to startup, False to remove
        """
        try:
            import winreg
            
            # Path to run.py
            script_path = os.path.join(os.path.dirname(__file__), '..', 'run.py')
            script_path = os.path.abspath(script_path)
            python_exe = sys.executable
            command = f'"{python_exe}" "{script_path}" --no-admin'
            
            # Open Run key
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            if enable:
                # Add to startup
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, 
                                   winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key, "SOKOL", 0, winreg.REG_SZ, command)
                return True
            else:
                # Remove from startup
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                       winreg.KEY_WRITE) as key:
                        winreg.DeleteValue(key, "SOKOL")
                    return True
                except WindowsError:
                    return False  # Already not in startup
                    
        except Exception as e:
            print(f"Startup registration failed: {e}")
            return False
    
    def is_startup_enabled(self) -> bool:
        """Check if SOKOL is registered for startup"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                               winreg.KEY_READ) as key:
                try:
                    winreg.QueryValueEx(key, "SOKOL")
                    return True
                except WindowsError:
                    return False
        except:
            return False
    
    def play_sound(self, sound_type: str = "notification"):
        """
        Play system sound
        
        Args:
            sound_type: notification, error, success, reminder
        """
        try:
            import winsound
            
            sounds = {
                "notification": winsound.MB_ICONEXCLAMATION,
                "error": winsound.MB_ICONHAND,
                "success": winsound.MB_OK,
                "reminder": winsound.MB_ICONASTERISK
            }
            
            sound = sounds.get(sound_type, winsound.MB_OK)
            winsound.MessageBeep(sound)
            return True
        except:
            return False
    
    def flash_window(self, hwnd: int = None, count: int = 5):
        """
        Flash window in taskbar to get attention
        
        Args:
            hwnd: Window handle (if None, uses console window)
            count: Number of flashes
        """
        if not WIN32_AVAILABLE:
            return False
        
        try:
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()
            
            # FLASHW_ALL = 3 (flash both window and taskbar)
            # FLASHW_TIMERNOFG = 12 (flash until foreground)
            class FLASHWINFO:
                def __init__(self):
                    self.cbSize = 20  # sizeof(FLASHWINFO)
                    self.hwnd = hwnd
                    self.dwFlags = 3  # FLASHW_ALL
                    self.uCount = count
                    self.dwTimeout = 0
            
            flash_info = FLASHWINFO()
            # Call FlashWindowEx
            win32gui.FlashWindowEx(flash_info.__dict__)
            return True
        except:
            return False


# Global instance
_windows_integration = None

def get_windows_integration() -> WindowsIntegration:
    """Get Windows integration instance"""
    global _windows_integration
    if _windows_integration is None:
        _windows_integration = WindowsIntegration()
    return _windows_integration


# Convenience functions
def notify(title: str, message: str, duration: int = 5):
    """Quick notification"""
    return get_windows_integration().show_notification(title, message, duration)

def sound(sound_type: str = "notification"):
    """Quick sound"""
    return get_windows_integration().play_sound(sound_type)

def register_startup(enable: bool = True):
    """Register/unregister startup"""
    return get_windows_integration().register_startup(enable)
