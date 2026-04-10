"""
Media control tool - Simple wrapper for media playback
"""

from typing import Any

import pyautogui


class MediaControlTool:
    """Tool for media control."""
    
    def play_pause(self) -> dict[str, Any]:
        """Toggle play/pause."""
        pyautogui.press("playpause")
        return {"success": True, "message": "Toggled play/pause"}
    
    def next_track(self) -> dict[str, Any]:
        """Skip to next track."""
        pyautogui.press("nexttrack")
        return {"success": True, "message": "Next track"}
    
    def previous_track(self) -> dict[str, Any]:
        """Go to previous track."""
        pyautogui.press("prevtrack")
        return {"success": True, "message": "Previous track"}
    
    def volume_up(self) -> dict[str, Any]:
        """Increase volume."""
        pyautogui.press("volumeup")
        return {"success": True, "message": "Volume up"}
    
    def volume_down(self) -> dict[str, Any]:
        """Decrease volume."""
        pyautogui.press("volumedown")
        return {"success": True, "message": "Volume down"}
    
    def mute(self) -> dict[str, Any]:
        """Toggle mute."""
        pyautogui.press("volumemute")
        return {"success": True, "message": "Toggled mute"}
