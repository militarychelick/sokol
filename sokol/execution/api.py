"""
API integrations - Browser, Steam, Discord, etc.
"""

from __future__ import annotations

import webbrowser
from typing import Any


class API:
    """API integrations for external services."""
    
    def open_url(self, url: str) -> bool:
        """Open URL in browser."""
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False
    
    def open_steam(self) -> bool:
        """Open Steam."""
        try:
            import subprocess
            subprocess.Popen(["steam://"])
            return True
        except Exception:
            return False
    
    def open_discord(self) -> bool:
        """Open Discord."""
        try:
            import subprocess
            subprocess.Popen(["discord://"])
            return True
        except Exception:
            return False
