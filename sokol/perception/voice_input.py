"""Voice input adapter - Whisper STT integration."""

from typing import Optional, Callable
from dataclasses import dataclass
import io

from sokol.observability.logging import get_logger

logger = get_logger("sokol.perception.voice_input")


@dataclass
class VoiceEvent:
    """Voice event data structure."""
    text: str
    confidence: float = 0.0
    is_final: bool = True


class VoiceInputAdapter:
    """
    Voice input adapter with Whisper STT integration.

    Provides speech-to-text functionality using Whisper model.
    """

    def __init__(self, wake_words: Optional[list[str]] = None, model_size: str = "base", backpressure_layer=None) -> None:
        """
        Initialize voice input adapter.

        Args:
            wake_words: List of wake words for activation (future use)
            model_size: Whisper model size (tiny, base, small, medium, large)
            backpressure_layer: Optional BackpressureLayer for adaptive throttling (Phase 2.1.1)
        """
        self._wake_words = wake_words or ["sokol"]
        self._model_size = model_size
        self._model = None
        self._available = self._check_availability()
        
        # Phase 2.1.1: Backpressure-aware throttling
        self._backpressure_layer = backpressure_layer
        self._throttled_count = 0
        
        logger.info_data(
            "Voice input adapter initialized",
            {"available": self._available, "model_size": model_size},
        )

    def _check_availability(self) -> bool:
        """Check if Whisper is available."""
        try:
            import whisper
            return True
        except ImportError:
            logger.warning("whisper not available, install with: pip install openai-whisper")
            return False

    def _load_model(self) -> None:
        """Load Whisper model lazily."""
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model(self._model_size)
                logger.info_data("Whisper model loaded", {"size": self._model_size})
            except Exception as e:
                logger.error_data("Failed to load Whisper model", {"error": str(e)})
                self._available = False

    def is_available(self) -> bool:
        """Check if voice input is available."""
        return self._available

    def transcribe(self, audio_data: bytes) -> VoiceEvent:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio data (WAV format)

        Returns:
            VoiceEvent with transcribed text.
        """
        if not self._available:
            logger.warning("Voice input not available")
            return VoiceEvent(text="", confidence=0.0, is_final=True)

        self._load_model()
        if self._model is None:
            return VoiceEvent(text="", confidence=0.0, is_final=True)

        try:
            # Convert bytes to audio file for Whisper
            import numpy as np
            import soundfile as sf

            audio, sr = sf.read(io.BytesIO(audio_data))
            
            # Transcribe
            result = self._model.transcribe(audio, fp16=False)
            text = result["text"].strip()
            
            # Extract confidence if available
            confidence = 0.0
            if "segments" in result and result["segments"]:
                avg_confidence = sum(seg.get("confidence", 0.0) for seg in result["segments"]) / len(result["segments"])
                confidence = avg_confidence

            # Phase 2.1.1: Check backpressure throttling
            if self._backpressure_layer:
                throttle_factor = self._backpressure_layer.get_throttle_factor()
                if throttle_factor < 0.5:
                    # Skip voice events under medium/high pressure
                    self._throttled_count += 1
                    logger.warning_data(
                        "Voice transcription throttled by backpressure",
                        {
                            "throttle_factor": throttle_factor,
                            "throttled_count": self._throttled_count
                        }
                    )
                    return VoiceEvent(text="", confidence=0.0, is_final=True)

            logger.info_data(
                "Voice transcription successful",
                {"text_length": len(text), "confidence": confidence},
            )
            
            return VoiceEvent(text=text, confidence=confidence, is_final=True)

        except ImportError as e:
            logger.error_data("Missing dependency for audio processing", {"error": str(e)})
            return VoiceEvent(text="", confidence=0.0, is_final=True)
        except Exception as e:
            logger.error_data("Voice transcription failed", {"error": str(e)})
            return VoiceEvent(text="", confidence=0.0, is_final=True)

    def set_callback(self, callback: Callable[[VoiceEvent], None]) -> None:
        """
        Set callback for voice events.

        Args:
            callback: Function to call on voice events
        """
        self._callback = callback
        logger.info("Voice callback set")

    def get_text(self, audio_data: bytes) -> str:
        """
        Get transcribed text from audio data.

        Args:
            audio_data: Raw audio data (WAV format)

        Returns:
            Transcribed text string (empty if not available).
        """
        event = self.transcribe(audio_data)
        return event.text
