"""
Speech-to-Text using Faster-Whisper
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from ..core.config import VoiceConfig
from ..core.exceptions import VoiceError


@dataclass
class TranscriptionResult:
    """Result of speech transcription."""
    text: str
    language: str
    language_probability: float
    segments: list[dict[str, Any]]
    duration: float


class SpeechToText:
    """
    Speech-to-Text using Faster-Whisper.
    
    Faster-Whisper is an optimized implementation using CTranslate2,
    providing faster inference than original Whisper.
    """
    
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._model: WhisperModel | None = None
        self._model_size = config.stt_model
    
    def initialize(self) -> None:
        """Load the Whisper model."""
        try:
            # Use GPU if available, otherwise CPU
            device = "cuda"  # Will fall back to CPU if not available
            
            self._model = WhisperModel(
                self._model_size,
                device=device,
                compute_type="auto",  # Automatically select best compute type
            )
        except Exception as e:
            raise VoiceError(f"Failed to load Whisper model '{self._model_size}'", str(e))
    
    def transcribe(
        self,
        audio_data: bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes (16kHz, 16-bit, mono)
            language: Language code (e.g., "ru", "en"). None for auto-detect.
        
        Returns:
            TranscriptionResult with text and metadata
        """
        if self._model is None:
            self.initialize()
        
        try:
            # Faster-Whisper expects numpy array or file path
            import numpy as np
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Transcribe
            segments, info = self._model.transcribe(
                audio_float,
                language=language or self.config.stt_language,
                beam_size=5,
                vad_filter=True,  # Use VAD to filter silence
            )
            
            # Collect segments
            segment_list = []
            full_text = ""
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                })
                full_text += segment.text
            
            return TranscriptionResult(
                text=full_text.strip(),
                language=info.language,
                language_probability=info.language_probability,
                segments=segment_list,
                duration=info.duration,
            )
            
        except Exception as e:
            raise VoiceError("Transcription failed", str(e))
    
    def transcribe_file(
        self,
        file_path: Path,
        language: str | None = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text.
        
        Args:
            file_path: Path to audio file
            language: Language code. None for auto-detect.
        
        Returns:
            TranscriptionResult with text and metadata
        """
        if self._model is None:
            self.initialize()
        
        try:
            segments, info = self._model.transcribe(
                str(file_path),
                language=language or self.config.stt_language,
                beam_size=5,
            )
            
            segment_list = []
            full_text = ""
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                })
                full_text += segment.text
            
            return TranscriptionResult(
                text=full_text.strip(),
                language=info.language,
                language_probability=info.language_probability,
                segments=segment_list,
                duration=info.duration,
            )
            
        except Exception as e:
            raise VoiceError(f"Failed to transcribe file: {file_path}", str(e))
    
    def shutdown(self) -> None:
        """Release model resources."""
        # Faster-Whisper doesn't need explicit cleanup
        self._model = None
