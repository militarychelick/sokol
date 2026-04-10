"""
Voice I/O - STT + TTS + wake word detection
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..core.config import Config


class VoiceIO:
    """Voice input/output with wake word detection."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._listening = False
        self._wake_word = config.voice.wake_word or "Сокол"
    
    async def initialize(self) -> None:
        """Initialize voice components."""
        # TODO: Initialize Faster-Whisper (STT)
        # TODO: Initialize Edge TTS (TTS)
        # TODO: Initialize wake word detection
        pass
    
    async def listen_for_wake_word(self) -> str | None:
        """Listen for wake word and return command."""
        # TODO: Implement wake word detection
        # For MVP, return None (use text input)
        return None
    
    async def listen(self) -> str | None:
        """Listen for voice input."""
        # TODO: Implement STT
        return None
    
    async def speak(self, text: str) -> None:
        """Speak text to user."""
        # TODO: Implement TTS
        print(f"[VOICE] {text}")
    
    async def shutdown(self) -> None:
        """Cleanup voice components."""
        pass
    
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self._listening
