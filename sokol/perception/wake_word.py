"""Wake word detection using Porcupine/Vosk."""

from typing import Optional, Callable
import threading
from dataclasses import dataclass

from sokol.observability.logging import get_logger

logger = get_logger("sokol.perception.wake_word")


@dataclass
class WakeWordEvent:
    """Wake word event data structure."""
    word: str
    confidence: float = 0.0
    audio_data: Optional[bytes] = None


class WakeWordDetector:
    """
    Wake word detector with Porcupine/Vosk integration.

    Detects wake words to trigger voice input.
    """

    def __init__(self, wake_words: Optional[list[str]] = None, engine: str = "porcupine", debounce_interval: float = 1.0, confidence_threshold: float = 0.0, backpressure_layer=None) -> None:
        """
        Initialize wake word detector.

        Args:
            wake_words: List of wake words for detection
            engine: Detection engine (porcupine, vosk)
            debounce_interval: Minimum seconds between wake word triggers (default: 1.0)
            confidence_threshold: Minimum confidence threshold for wake word detection (default: 0.0 = accept all)
            backpressure_layer: Optional BackpressureLayer for adaptive throttling (Phase 2.1.1)
        """
        self._wake_words = wake_words or ["sokol"]
        self._engine = engine
        self._available = self._check_availability()
        self._detector = None
        self._callback: Optional[Callable[[WakeWordEvent], None]] = None
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # P0: Debounce/rate limiting
        self._debounce_interval = debounce_interval
        self._last_trigger_time = 0.0
        self._dropped_count = 0
        
        # P2: Confidence threshold for production-level filtering
        self._confidence_threshold = confidence_threshold
        
        # Phase 2.1.1: Backpressure-aware throttling
        self._backpressure_layer = backpressure_layer
        self._throttled_count = 0

        logger.info_data(
            "Wake word detector initialized",
            {"available": self._available, "engine": engine, "wake_words": self._wake_words, "debounce_interval": debounce_interval},
        )

    def _check_availability(self) -> bool:
        """Check if wake word engine is available."""
        if self._engine == "porcupine":
            try:
                import pvporcupine
                return True
            except ImportError:
                logger.warning("pvporcupine not available, install with: pip install pvporcupine")
                return False
        elif self._engine == "vosk":
            try:
                import vosk
                return True
            except ImportError:
                logger.warning("vosk not available, install with: pip install vosk")
                return False
        return False

    def _load_detector(self) -> None:
        """Load wake word detector."""
        if self._detector is not None:
            return

        try:
            if self._engine == "porcupine":
                import pvporcupine

                # Try to load Porcupine with access key if available
                access_key = None  # Would come from config/env
                self._detector = pvporcupine.create(
                    keyword_paths=[],
                    access_key=access_key,
                    keywords=self._wake_words,
                )
                logger.info("Porcupine detector loaded")

            elif self._engine == "vosk":
                # Vosk implementation would go here
                # For now, mark as not implemented
                logger.warning("Vosk wake word detection not yet implemented")
                self._available = False

        except Exception as e:
            logger.error_data("Failed to load wake word detector", {"error": str(e)})
            self._available = False

    def is_available(self) -> bool:
        """Check if wake word detection is available."""
        return self._available

    def set_callback(self, callback: Callable[[WakeWordEvent], None]) -> None:
        """
        Set callback for wake word events.

        Args:
            callback: Function to call on wake word detection
        """
        self._callback = callback
        logger.info("Wake word callback set")

    def start_listening(self) -> bool:
        """
        Start continuous listening for wake words.

        Returns:
            True if started successfully, False otherwise
        """
        if not self._available:
            logger.warning("Wake word detection not available")
            return False

        # Continuous listener is not fully implemented yet; expose this explicitly.
        logger.warning(
            "Continuous wake-word listening is not implemented; use detect(audio_data) path"
        )
        return False

        with self._lock:
            if self._listening:
                logger.warning("Already listening")
                return False

            return False

    def stop_listening(self) -> None:
        """Stop continuous listening for wake words."""
        with self._lock:
            if not self._listening:
                return

            self._listening = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            logger.info("Wake word listening stopped")

    def _listen_loop(self) -> None:
        """Main listening loop (runs in background thread)."""
        logger.info("Wake word listening loop started")

        # This is a simplified implementation
        # Real implementation would use audio input stream and process audio frames
        # For now, this is a placeholder for the actual wake word detection logic

        while self._listening:
            try:
                # TODO: Implement actual audio capture and wake word detection
                # This would involve:
                # 1. Capturing audio from microphone
                # 2. Processing audio frames through detector
                # 3. Calling callback when wake word detected

                # Placeholder: sleep to avoid busy loop
                import time
                time.sleep(0.1)

            except Exception as e:
                logger.error_data("Wake word listening loop error", {"error": str(e)})
                break

        logger.info("Wake word listening loop stopped")

    def detect(self, audio_data: bytes) -> WakeWordEvent:
        """
        Detect wake word in audio data (manual trigger).

        Args:
            audio_data: Raw audio data

        Returns:
            WakeWordEvent with detection result
        """
        if not self._available:
            return WakeWordEvent(word="", confidence=0.0)

        self._load_detector()
        if self._detector is None:
            return WakeWordEvent(word="", confidence=0.0)

        try:
            if self._engine == "porcupine":
                import numpy as np
                import time

                # Convert audio data to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)

                # Process through Porcupine
                # This is simplified - real implementation would handle sample rate and frame size
                result = self._detector.process(audio_array)

                if result >= 0:
                    # P0: Debounce check
                    current_time = time.time()
                    time_since_last = current_time - self._last_trigger_time
                    
                    if time_since_last < self._debounce_interval:
                        # Drop this trigger due to debounce
                        self._dropped_count += 1
                        logger.warning_data(
                            "Wake word dropped by debounce",
                            {
                                "time_since_last": f"{time_since_last:.2f}s",
                                "debounce_interval": self._debounce_interval,
                                "dropped_count": self._dropped_count
                            }
                        )
                        return WakeWordEvent(word="", confidence=0.0)
                    
                    # Accept this trigger
                    self._last_trigger_time = current_time
                    word = self._wake_words[result] if result < len(self._wake_words) else self._wake_words[0]
                    confidence = 1.0  # Porcupine returns 0/1 for detection
                    
                    # P2: Check confidence threshold
                    if confidence < self._confidence_threshold:
                        self._dropped_count += 1
                        logger.warning_data(
                            "Wake word dropped by confidence threshold",
                            {
                                "word": word,
                                "confidence": confidence,
                                "threshold": self._confidence_threshold,
                                "dropped_count": self._dropped_count
                            }
                        )
                        return WakeWordEvent(word="", confidence=confidence)
                    
                    # Phase 2.1.1: Check backpressure throttling
                    # FIXED: Remove random-based throttling for determinism
                    # Use deterministic counter-based throttling instead
                    if self._backpressure_layer:
                        throttle_factor = self._backpressure_layer.get_throttle_factor()
                        if throttle_factor < 1.0:
                            # Deterministic throttling: skip every Nth trigger based on throttle_factor
                            # throttle_factor < 1.0 means we skip some triggers
                            # throttle_factor = 0.5 means we skip every 2nd trigger
                            # throttle_factor = 0.1 means we skip 9 out of 10 triggers
                            skip_interval = int(1.0 / throttle_factor) if throttle_factor > 0 else 1
                            self._throttled_count += 1
                            if self._throttled_count % skip_interval != 0:
                                logger.warning_data(
                                    "Wake word throttled by backpressure (deterministic)",
                                    {
                                        "word": word,
                                        "throttle_factor": throttle_factor,
                                        "throttled_count": self._throttled_count,
                                        "skip_interval": skip_interval
                                    }
                                )
                                return WakeWordEvent(word="", confidence=confidence)
                    
                    logger.info_data("Wake word detected", {"word": word, "dropped_count": self._dropped_count})
                    return WakeWordEvent(word=word, confidence=confidence, audio_data=audio_data)

            return WakeWordEvent(word="", confidence=0.0)

        except Exception as e:
            logger.error_data("Wake word detection failed", {"error": str(e)})
            return WakeWordEvent(word="", confidence=0.0)
    
    def get_dropped_count(self) -> int:
        """
        Get the number of wake word triggers dropped by debounce.
        
        Returns:
            Number of dropped triggers
        """
        return self._dropped_count
    
    def reset_dropped_count(self) -> None:
        """Reset the dropped trigger counter."""
        self._dropped_count = 0
