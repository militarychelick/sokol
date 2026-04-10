"""
STT (Speech-to-Text) - Faster-Whisper wrapper
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config


class STT:
    """Speech-to-Text using Faster-Whisper."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._model = None
    
    async def initialize(self) -> None:
        """Initialize Faster-Whisper model."""
        # TODO: Initialize faster-whisper model
        # from faster_whisper import WhisperModel
        # self._model = WhisperModel(self.config.voice.stt_model)
        pass
    
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio to text."""
        # TODO: Implement transcription
        return ""
    
    async def shutdown(self) -> None:
        """Cleanup model."""
        pass
