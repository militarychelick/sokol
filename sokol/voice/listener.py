"""
Audio capture with Voice Activity Detection (VAD)
"""

from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import Callable

import pyaudio
import webrtcvad

from ..core.config import VoiceConfig
from ..core.exceptions import VoiceError


@dataclass
class AudioChunk:
    """A chunk of audio data."""
    data: bytes
    timestamp: float
    is_speech: bool


class AudioListener:
    """
    Captures audio with Voice Activity Detection.
    
    Uses WebRTC VAD for efficient speech detection.
    Only sends speech audio to STT, ignoring silence.
    """
    
    # Audio parameters
    SAMPLE_RATE = 16000  # Whisper expects 16kHz
    FRAME_DURATION_MS = 30  # WebRTC VAD supports 10, 20, or 30ms
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
    
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self.vad = webrtcvad.Vad(config.vad_sensitivity)
        
        self._audio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._is_listening = False
        self._audio_queue: queue.Queue[AudioChunk | None] = queue.Queue()
        self._listen_thread: threading.Thread | None = None
        
        # Callbacks
        self._on_speech_start: Callable[[], None] | None = None
        self._on_speech_end: Callable[[], None] | None = None
    
    def initialize(self) -> None:
        """Initialize audio system."""
        try:
            self._audio = pyaudio.PyAudio()
        except Exception as e:
            raise VoiceError("Failed to initialize audio system", str(e))
    
    def shutdown(self) -> None:
        """Shutdown audio system."""
        self.stop_listening()
        
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        if self._audio:
            self._audio.terminate()
            self._audio = None
    
    def start_listening(self) -> None:
        """Start continuous audio capture."""
        if self._is_listening:
            return
        
        if self._audio is None:
            self.initialize()
        
        try:
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.FRAME_SIZE,
            )
        except Exception as e:
            raise VoiceError("Failed to open audio stream", str(e))
        
        self._is_listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
    
    def stop_listening(self) -> None:
        """Stop audio capture."""
        self._is_listening = False
        
        # Signal end of stream
        self._audio_queue.put(None)
        
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
    
    def on_speech_start(self, callback: Callable[[], None]) -> None:
        """Register callback for speech start detection."""
        self._on_speech_start = callback
    
    def on_speech_end(self, callback: Callable[[], None]) -> None:
        """Register callback for speech end detection."""
        self._on_speech_end = callback
    
    def get_audio_chunk(self, timeout: float = 1.0) -> AudioChunk | None:
        """Get next audio chunk from queue."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_speech_audio(self, timeout: float = 30.0) -> bytes | None:
        """
        Capture a complete speech segment.
        
        Returns when speech is detected and then silence for a period.
        """
        frames: list[bytes] = []
        speech_frames = 0
        silence_frames = 0
        in_speech = False
        
        # Minimum speech frames to consider valid
        min_speech_frames = int(0.3 / (self.FRAME_DURATION_MS / 1000))  # 300ms
        # Silence to end speech
        silence_to_end = int(0.5 / (self.FRAME_DURATION_MS / 1000))  # 500ms
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                break
            
            chunk = self.get_audio_chunk(timeout=0.1)
            if chunk is None:
                continue
            
            if chunk.is_speech:
                frames.append(chunk.data)
                speech_frames += 1
                
                if not in_speech and speech_frames >= min_speech_frames:
                    in_speech = True
                    if self._on_speech_start:
                        self._on_speech_start()
                
                silence_frames = 0
            else:
                if in_speech:
                    frames.append(chunk.data)  # Include trailing silence
                    silence_frames += 1
                    
                    if silence_frames >= silence_to_end:
                        # Speech ended
                        if self._on_speech_end:
                            self._on_speech_end()
                        break
        
        if frames and speech_frames >= min_speech_frames:
            return b"".join(frames)
        
        return None
    
    def _listen_loop(self) -> None:
        """Continuous audio capture loop."""
        import time
        
        while self._is_listening:
            try:
                if self._stream is None:
                    break
                
                data = self._stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                
                # Check if speech
                is_speech = self.vad.is_speech(data, self.SAMPLE_RATE)
                
                chunk = AudioChunk(
                    data=data,
                    timestamp=time.time(),
                    is_speech=is_speech,
                )
                
                self._audio_queue.put(chunk)
                
            except OSError as e:
                # Stream error, stop listening
                self._is_listening = False
                break
            except Exception:
                # Other errors, continue
                pass
