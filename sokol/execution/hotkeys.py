"""
Hotkeys - Fallback for simple actions
"""

from __future__ import annotations

import pyautogui
from typing import Any


class Hotkeys:
    """Hotkey execution."""
    
    def press(self, keys: list[str]) -> bool:
        """Press hotkey combination."""
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            return False
