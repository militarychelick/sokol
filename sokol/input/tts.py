"""
TTS (Text-to-Speech) - Edge TTS wrapper
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config


class TTS:
    """Text-to-Speech using Edge TTS."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    async def initialize(self) -> None:
        """Initialize Edge TTS."""
        # TODO: Initialize edge-tts
        # import edge_tts
        pass
    
    async def speak(self, text: str) -> None:
        """Speak text."""
        # TODO: Implement TTS
        print(f"[TTS] {text}")
    
    async def shutdown(self) -> None:
        """Cleanup TTS."""
        pass
