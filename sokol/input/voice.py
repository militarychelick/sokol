"""
Voice I/O - Optional voice interface for Sokol v2
"""

from __future__ import annotations

from typing import Any


class VoiceIO:
    """Voice input/output (optional, text fallback required)."""
    
    def __init__(self, config: Any) -> None:
        self.config = config
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize voice components (STT/TTS)."""
        # For v2, voice is optional - may fail without hardware
        try:
            # TODO: Initialize Faster-Whisper (STT)
            # TODO: Initialize Edge TTS (TTS)
            self._initialized = True
        except Exception:
            self._initialized = False
    
    async def shutdown(self) -> None:
        """Cleanup voice components."""
        pass
    
    async def listen(self) -> str | None:
        """Listen for voice input."""
        if not self._initialized:
            return None
        # TODO: Implement STT
        return None
    
    async def speak(self, text: str) -> None:
        """Speak text to user."""
        if not self._initialized:
            return
        # TODO: Implement TTS
