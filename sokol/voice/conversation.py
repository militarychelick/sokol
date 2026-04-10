"""
Voice interaction layer - coordinates listening, STT, and TTS
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ..core.config import VoiceConfig
from ..core.exceptions import VoiceError
from .listener import AudioListener
from .stt import SpeechToText
from .tts import TextToSpeech


class VoiceLayer:
    """
    Coordinates voice interaction flow.
    
    This is the main interface for voice I/O:
    - Listen for user speech
    - Transcribe to text
    - Synthesize responses
    """
    
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        
        self.listener = AudioListener(config)
        self.stt = SpeechToText(config)
        self.tts = TextToSpeech(config)
        
        self._is_speaking = False
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        
        # Callbacks
        self._on_listening_start: Callable[[], None] | None = None
        self._on_listening_end: Callable[[], None] | None = None
        self._on_speech_detected: Callable[[], None] | None = None
    
    async def initialize(self) -> None:
        """Initialize voice components."""
        try:
            # Initialize listener
            self.listener.initialize()
        except Exception:
            # Voice hardware not available, will use text only
            pass
        
        # Initialize TTS
        try:
            await self.tts.initialize()
        except Exception:
            # TTS not available, will use text output
            pass
        
        # Set up VAD callbacks
        self.listener.on_speech_start(self._handle_speech_start)
        self.listener.on_speech_end(self._handle_speech_end)
    
    async def shutdown(self) -> None:
        """Shutdown voice components."""
        self.listener.stop_listening()
        self.listener.shutdown()
        self.stt.shutdown()
        self.tts.shutdown()
    
    def on_listening_start(self, callback: Callable[[], None]) -> None:
        """Register callback for when listening starts."""
        self._on_listening_start = callback
    
    def on_listening_end(self, callback: Callable[[], None]) -> None:
        """Register callback for when listening ends."""
        self._on_listening_end = callback
    
    def on_speech_detected(self, callback: Callable[[], None]) -> None:
        """Register callback for when speech is detected."""
        self._on_speech_detected = callback
    
    async def listen_for_input(self, timeout: float = 30.0) -> str | None:
        """
        Listen for user voice input.
        
        This is the main entry point for getting voice input.
        Uses push-to-talk or wake word depending on config.
        
        Args:
            timeout: Maximum time to wait for input
        
        Returns:
            Transcribed text or None if no input
        """
        if self._is_speaking:
            return None  # Don't listen while speaking
        
        try:
            # Notify listening started
            if self._on_listening_start:
                self._on_listening_start()
            
            # Start continuous listening
            self.listener.start_listening()
            
            # Wait for speech segment
            audio = self.listener.get_speech_audio(timeout=timeout)
            
            if audio is None:
                return None
            
            # Transcribe
            result = self.stt.transcribe(audio)
            
            if result.text:
                return result.text
            
            return None
            
        except Exception:
            # Voice input failed, return None (will fall back to text)
            return None
        finally:
            try:
                self.listener.stop_listening()
            except Exception:
                pass
            
            if self._on_listening_end:
                try:
                    self._on_listening_end()
                except Exception:
                    pass
    
    async def speak(self, text: str) -> None:
        """
        Speak text to user.
        
        Args:
            text: Text to speak
        """
        if not text:
            return
        
        self._is_speaking = True
        
        try:
            await self.tts.speak(text)
        finally:
            self._is_speaking = False
    
    async def speak_async(self, text: str) -> asyncio.Task:
        """
        Speak text asynchronously.
        
        Returns immediately, speech plays in background.
        
        Args:
            text: Text to speak
        
        Returns:
            Task that completes when speech is done
        """
        return asyncio.create_task(self.speak(text))
    
    def _handle_speech_start(self) -> None:
        """Handle speech start event from VAD."""
        if self._on_speech_detected:
            self._on_speech_detected()
    
    def _handle_speech_end(self) -> None:
        """Handle speech end event from VAD."""
        pass  # Handled in get_speech_audio
    
    # --- Push-to-Talk Support ---
    
    async def wait_for_ptt(self, key: str = "f12") -> None:
        """
        Wait for push-to-talk key press.
        
        This is used when wake word is disabled.
        """
        import keyboard
        
        # Wait for key press
        event = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: keyboard.read_event(key, suppress=True),
        )
        
        if event.event_type == keyboard.KEY_DOWN:
            # Key pressed, start listening
            await self.listen_for_input()
    
    # --- Wake Word Support (Optional) ---
    
    async def listen_for_wake_word(self, wake_word: str = "hey sokol") -> bool:
        """
        Listen continuously for wake word.
        
        Returns True when wake word is detected.
        """
        self.listener.start_listening()
        
        try:
            while True:
                audio = self.listener.get_speech_audio(timeout=60.0)
                
                if audio:
                    result = self.stt.transcribe(audio)
                    text = result.text.lower()
                    
                    if wake_word in text:
                        return True
            
        finally:
            self.listener.stop_listening()
        
        return False
