"""Live loop controller for continuous agent operation."""

import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from sokol.runtime.unified_input import UnifiedInputContext
from sokol.runtime.orchestrator import Orchestrator
from sokol.perception.voice_input import VoiceInputAdapter, VoiceEvent
from sokol.perception.screen_input import ScreenInputAdapter
from sokol.perception.wake_word import WakeWordDetector, WakeWordEvent
from sokol.core.types import AgentState
from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.live_loop")


class LoopEventType(Enum):
    """Types of events in the live loop."""
    TEXT_INPUT = "text_input"
    VOICE_INPUT = "voice_input"
    WAKE_WORD = "wake_word"
    SCREEN_CAPTURE = "screen_capture"
    STOP = "stop"


@dataclass
class LoopEvent:
    """Event in the live loop."""
    event_type: LoopEventType
    data: Optional[dict] = None
    callback: Optional[Callable] = None


class LiveLoopController:
    """
    Live loop controller for continuous agent operation.
    
    Manages the PERCEPTION → DECISION → ACTION → OBSERVATION → MEMORY → LOOP cycle.
    """
    
    def __init__(
        self,
        orchestrator: Orchestrator,
        voice_input: Optional[VoiceInputAdapter] = None,
        screen_input: Optional[ScreenInputAdapter] = None,
        wake_word_detector: Optional[WakeWordDetector] = None,
    ) -> None:
        """
        Initialize live loop controller.
        
        Args:
            orchestrator: Orchestrator instance
            voice_input: VoiceInputAdapter instance (optional)
            screen_input: ScreenInputAdapter instance (optional)
            wake_word_detector: WakeWordDetector instance (optional)
        """
        self._orchestrator = orchestrator
        self._voice_input = voice_input
        self._screen_input = screen_input
        self._wake_word_detector = wake_word_detector
        
        # Event queue for single-threaded processing (bounded to prevent OOM)
        self._event_queue = queue.Queue(maxsize=100)
        
        # Control flags
        self._running = False
        self._paused = False
        self._paused_event_buffer: list[LoopEvent] = []  # Buffer events during pause
        self._MAX_PAUSED_BUFFER = 50  # Limit to prevent memory growth
        
        # Queue drop tracking for monitoring
        self._queue_drop_count = 0
        self._loop_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._on_state_change: Optional[Callable[[AgentState], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None
        
        logger.info("Live loop controller initialized")
    
    def set_state_change_callback(self, callback: Callable[[AgentState], None]) -> None:
        """Set callback for agent state changes."""
        self._on_state_change = callback
    
    def set_response_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for agent responses."""
        self._on_response = callback
    
    def start(self) -> None:
        """Start the live loop."""
        with self._lock:
            if self._running:
                logger.warning("Live loop already running")
                return
            
            self._running = True
            self._paused = False
            self._loop_thread = threading.Thread(
                target=self._loop_main,
                daemon=True,
                name="LiveLoopController"
            )
            self._loop_thread.start()
            
            # Start wake word detection if available
            if self._wake_word_detector and self._wake_word_detector.is_available():
                self._wake_word_detector.set_callback(self._on_wake_word)
                self._wake_word_detector.start_listening()
            
            logger.info("Live loop started")
    
    def stop(self) -> None:
        """Stop the live loop."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Send stop event
            self._event_queue.put(LoopEvent(LoopEventType.STOP))
        
        # Stop wake word detection
        if self._wake_word_detector:
            self._wake_word_detector.stop_listening()
        
        # Wait for loop thread to finish
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)
        
        logger.info("Live loop stopped")
    
    def pause(self) -> None:
        """Pause the live loop (stop processing but keep running)."""
        with self._lock:
            self._paused = True
            self._paused_event_buffer.clear()  # Clear any previous buffer
        logger.info("Live loop paused")
    
    def resume(self) -> None:
        """Resume the live loop and replay buffered events."""
        with self._lock:
            self._paused = False
            # Replay buffered events back to queue
            for buffered_event in self._paused_event_buffer:
                try:
                    self._event_queue.put_nowait(buffered_event)
                except queue.Full:
                    self._queue_drop_count += 1
                    logger.warning_data("Buffered event dropped on resume - queue full",
                        {"drop_count": self._queue_drop_count})
            buffer_count = len(self._paused_event_buffer)
            self._paused_event_buffer.clear()
        logger.info_data("Live loop resumed", {"replayed_events": buffer_count})
    
    def submit_text(self, text: str) -> None:
        """Submit text input to the loop."""
        event = LoopEvent(
            LoopEventType.TEXT_INPUT,
            data={"text": text}
        )
        try:
            self._event_queue.put_nowait(event)
            logger.debug(f"Text input submitted: {text[:50]}...")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Text event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def submit_voice(self, audio_data: bytes) -> None:
        """Submit voice audio to the loop."""
        event = LoopEvent(
            LoopEventType.VOICE_INPUT,
            data={"audio": audio_data}
        )
        try:
            self._event_queue.put_nowait(event)
            logger.debug("Voice input submitted")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Voice event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def request_screen_capture(self) -> None:
        """Request screen capture in the next cycle."""
        event = LoopEvent(LoopEventType.SCREEN_CAPTURE)
        try:
            self._event_queue.put_nowait(event)
            logger.debug("Screen capture requested")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Screen capture event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def _loop_main(self) -> None:
        """Main loop thread."""
        logger.info("Live loop thread started")
        
        while self._running:
            try:
                # Wait for event with timeout to allow periodic checks
                try:
                    event = self._event_queue.get(timeout=0.1)
                except queue.Empty:
                    # No event, continue loop
                    continue
                
                # Handle stop event
                if event.event_type == LoopEventType.STOP:
                    break
                
                # Buffer event if paused (with size limit)
                if self._paused:
                    if len(self._paused_event_buffer) < self._MAX_PAUSED_BUFFER:
                        self._paused_event_buffer.append(event)
                    else:
                        self._queue_drop_count += 1
                        logger.warning_data(
                            "Paused buffer full, event dropped",
                            {"buffer_size": len(self._paused_event_buffer), 
                             "max_buffer": self._MAX_PAUSED_BUFFER,
                             "drop_count": self._queue_drop_count}
                        )
                    continue
                
                # Process event
                self._process_event(event)
                
                # Log queue size for monitoring
                queue_size = self._event_queue.qsize()
                if queue_size > 50:
                    logger.warning_data("Event queue near capacity",
                        {"queue_size": queue_size, "maxsize": 100, "drops": self._queue_drop_count})
                elif queue_size > 10:
                    logger.warning_data("Event queue backing up", {"queue_size": queue_size})
                
            except Exception as e:
                logger.error_data("Loop error", {"error": str(e), "traceback": str(e.__traceback__)})
                # Continue loop despite errors
        
        logger.info("Live loop thread stopped")
    
    def _process_event(self, event: LoopEvent) -> None:
        """Process a single event."""
        # Update state to thinking
        self._update_state(AgentState.THINKING)
        
        # Build unified input context
        context = self._build_context(event)
        
        if context.is_empty():
            logger.warning("Empty context, skipping")
            return
        
        logger.debug_data(
            "Processing event",
            {"type": event.event_type.value, "context": context.to_dict()}
        )
        
        # Process through orchestrator
        try:
            # Build screen context dict if available
            screen_context_dict = None
            if context.has_screen and context.screen_snapshot:
                screen_context_dict = {
                    "active_window": context.screen_snapshot.active_window,
                    "has_image": context.screen_snapshot.image_bytes is not None,
                    "element_count": len(context.screen_snapshot.elements),
                }

            response = self._orchestrator.process_input(
                text=context.get_primary_text(),
                source=context.source,
                screen_context=screen_context_dict,
            )
            
            # Update state to idle
            self._update_state(AgentState.IDLE)
            
            # Send response callback
            if self._on_response:
                self._on_response(response.formatted_message)
            
            # Memory feedback loop is handled by orchestrator internally
            # through MemoryManager integration
            
        except Exception as e:
            logger.error_data("Orchestrator error", {"error": str(e)})
            self._update_state(AgentState.ERROR)
    
    def _build_context(self, event: LoopEvent) -> UnifiedInputContext:
        """Build unified input context from event."""
        if event.event_type == LoopEventType.TEXT_INPUT:
            text = event.data.get("text", "") if event.data else ""
            return UnifiedInputContext.from_text(text)
        
        elif event.event_type == LoopEventType.VOICE_INPUT:
            # Check if text is already transcribed (from wake word)
            if event.data and "text" in event.data:
                text = event.data.get("text", "")
                confidence = event.data.get("confidence", 0.0)
                return UnifiedInputContext(voice_text=text, voice_confidence=confidence, source="voice")
            # Otherwise, transcribe audio
            audio = event.data.get("audio") if event.data else None
            if audio and self._voice_input:
                voice_event = self._voice_input.transcribe(audio)
                return UnifiedInputContext.from_voice(voice_event)
            return UnifiedInputContext()
        
        elif event.event_type == LoopEventType.WAKE_WORD:
            # Wake word detected without audio, just log
            logger.info("Wake word detected (no audio)")
            return UnifiedInputContext()
        
        elif event.event_type == LoopEventType.SCREEN_CAPTURE:
            if self._screen_input and self._screen_input.is_available():
                snapshot = self._screen_input.capture()
                return UnifiedInputContext.from_screen(snapshot)
            return UnifiedInputContext()
        
        return UnifiedInputContext()
    
    def _on_wake_word(self, event: WakeWordEvent) -> None:
        """Handle wake word detection - automatically trigger voice capture."""
        logger.info_data("Wake word detected", {"word": event.word})
        
        # If audio data is provided, transcribe it directly
        if event.audio_data and self._voice_input:
            voice_event = self._voice_input.transcribe(event.audio_data)
            if voice_event.text:
                # Submit voice transcription to loop
                loop_event = LoopEvent(
                    LoopEventType.VOICE_INPUT,
                    data={"text": voice_event.text, "confidence": voice_event.confidence}
                )
                self._event_queue.put(loop_event)
                return
        
        # Otherwise, submit wake word event to trigger manual voice capture
        loop_event = LoopEvent(
            LoopEventType.WAKE_WORD,
            data={"word": event.word}
        )
        self._event_queue.put(loop_event)
    
    def _update_state(self, state: AgentState) -> None:
        """Update agent state and notify callback."""
        if self._on_state_change:
            self._on_state_change(state)
    
    def is_running(self) -> bool:
        """Check if loop is running."""
        return self._running
    
    def is_paused(self) -> bool:
        """Check if loop is paused."""
        return self._paused

"""Live loop controller for continuous agent operation."""

import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from sokol.runtime.unified_input import UnifiedInputContext
from sokol.runtime.orchestrator import Orchestrator
from sokol.perception.voice_input import VoiceInputAdapter, VoiceEvent
from sokol.perception.screen_input import ScreenInputAdapter
from sokol.perception.wake_word import WakeWordDetector, WakeWordEvent
from sokol.core.types import AgentState
from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.live_loop")


class LoopEventType(Enum):
    """Types of events in the live loop."""
    TEXT_INPUT = "text_input"
    VOICE_INPUT = "voice_input"
    WAKE_WORD = "wake_word"
    SCREEN_CAPTURE = "screen_capture"
    STOP = "stop"


@dataclass
class LoopEvent:
    """Event in the live loop."""
    event_type: LoopEventType
    data: Optional[dict] = None
    callback: Optional[Callable] = None


class LiveLoopController:
    """
    Live loop controller for continuous agent operation.
    
    Manages the PERCEPTION → DECISION → ACTION → OBSERVATION → MEMORY → LOOP cycle.
    """
    
    def __init__(
        self,
        orchestrator: Orchestrator,
        voice_input: Optional[VoiceInputAdapter] = None,
        screen_input: Optional[ScreenInputAdapter] = None,
        wake_word_detector: Optional[WakeWordDetector] = None,
    ) -> None:
        """
        Initialize live loop controller.
        
        Args:
            orchestrator: Orchestrator instance
            voice_input: VoiceInputAdapter instance (optional)
            screen_input: ScreenInputAdapter instance (optional)
            wake_word_detector: WakeWordDetector instance (optional)
        """
        self._orchestrator = orchestrator
        self._voice_input = voice_input
        self._screen_input = screen_input
        self._wake_word_detector = wake_word_detector
        
        # Event queue for single-threaded processing (bounded to prevent OOM)
        self._event_queue = queue.Queue(maxsize=100)
        
        # Control flags
        self._running = False
        self._paused = False
        self._paused_event_buffer: list[LoopEvent] = []  # Buffer events during pause
        self._MAX_PAUSED_BUFFER = 50  # Limit to prevent memory growth
        
        # Queue drop tracking for monitoring
        self._queue_drop_count = 0
        self._loop_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._on_state_change: Optional[Callable[[AgentState], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None
        
        logger.info("Live loop controller initialized")
    
    def set_state_change_callback(self, callback: Callable[[AgentState], None]) -> None:
        """Set callback for agent state changes."""
        self._on_state_change = callback
    
    def set_response_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for agent responses."""
        self._on_response = callback
    
    def start(self) -> None:
        """Start the live loop."""
        with self._lock:
            if self._running:
                logger.warning("Live loop already running")
                return
            
            self._running = True
            self._paused = False
            self._loop_thread = threading.Thread(
                target=self._loop_main,
                daemon=True,
                name="LiveLoopController"
            )
            self._loop_thread.start()
            
            # Start wake word detection if available
            if self._wake_word_detector and self._wake_word_detector.is_available():
                self._wake_word_detector.set_callback(self._on_wake_word)
                self._wake_word_detector.start_listening()
            
            logger.info("Live loop started")
    
    def stop(self) -> None:
        """Stop the live loop."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Send stop event
            self._event_queue.put(LoopEvent(LoopEventType.STOP))
        
        # Stop wake word detection
        if self._wake_word_detector:
            self._wake_word_detector.stop_listening()
        
        # Wait for loop thread to finish
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)
        
        logger.info("Live loop stopped")
    
    def pause(self) -> None:
        """Pause the live loop (stop processing but keep running)."""
        with self._lock:
            self._paused = True
            self._paused_event_buffer.clear()  # Clear any previous buffer
        logger.info("Live loop paused")
    
    def resume(self) -> None:
        """Resume the live loop and replay buffered events."""
        with self._lock:
            self._paused = False
            # Replay buffered events back to queue
            for buffered_event in self._paused_event_buffer:
                try:
                    self._event_queue.put_nowait(buffered_event)
                except queue.Full:
                    self._queue_drop_count += 1
                    logger.warning_data("Buffered event dropped on resume - queue full",
                        {"drop_count": self._queue_drop_count})
            buffer_count = len(self._paused_event_buffer)
            self._paused_event_buffer.clear()
        logger.info_data("Live loop resumed", {"replayed_events": buffer_count})
    
    def submit_text(self, text: str) -> None:
        """Submit text input to the loop."""
        event = LoopEvent(
            LoopEventType.TEXT_INPUT,
            data={"text": text}
        )
        try:
            self._event_queue.put_nowait(event)
            logger.debug(f"Text input submitted: {text[:50]}...")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Text event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def submit_voice(self, audio_data: bytes) -> None:
        """Submit voice audio to the loop."""
        event = LoopEvent(
            LoopEventType.VOICE_INPUT,
            data={"audio": audio_data}
        )
        try:
            self._event_queue.put_nowait(event)
            logger.debug("Voice input submitted")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Voice event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def request_screen_capture(self) -> None:
        """Request screen capture in the next cycle."""
        event = LoopEvent(LoopEventType.SCREEN_CAPTURE)
        try:
            self._event_queue.put_nowait(event)
            logger.debug("Screen capture requested")
        except queue.Full:
            self._queue_drop_count += 1
            logger.warning_data("Screen capture event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
    
    def _loop_main(self) -> None:
        """Main loop thread."""
        logger.info("Live loop thread started")
        
        while self._running:
            try:
                # Wait for event with timeout to allow periodic checks
                try:
                    event = self._event_queue.get(timeout=0.1)
                except queue.Empty:
                    # No event, continue loop
                    continue
                
                # Handle stop event
                if event.event_type == LoopEventType.STOP:
                    break
                
                # Buffer event if paused (with size limit)
                if self._paused:
                    if len(self._paused_event_buffer) < self._MAX_PAUSED_BUFFER:
                        self._paused_event_buffer.append(event)
                    else:
                        self._queue_drop_count += 1
                        logger.warning_data(
                            "Paused buffer full, event dropped",
                            {"buffer_size": len(self._paused_event_buffer), 
                             "max_buffer": self._MAX_PAUSED_BUFFER,
                             "drop_count": self._queue_drop_count}
                        )
                    continue
                
                # Process event
                self._process_event(event)
                
                # Log queue size for monitoring
                queue_size = self._event_queue.qsize()
                if queue_size > 50:
                    logger.warning_data("Event queue near capacity",
                        {"queue_size": queue_size, "maxsize": 100, "drops": self._queue_drop_count})
                elif queue_size > 10:
                    logger.warning_data("Event queue backing up", {"queue_size": queue_size})
                
            except Exception as e:
                logger.error_data("Loop error", {"error": str(e), "traceback": str(e.__traceback__)})
                # Continue loop despite errors
        
        logger.info("Live loop thread stopped")
    
    def _process_event(self, event: LoopEvent) -> None:
        """Process a single event."""
        # Update state to thinking
        self._update_state(AgentState.THINKING)
        
        # Build unified input context
        context = self._build_context(event)
        
        if context.is_empty():
            logger.warning("Empty context, skipping")
            return
        
        logger.debug_data(
            "Processing event",
            {"type": event.event_type.value, "context": context.to_dict()}
        )
        
        # Process through orchestrator
        try:
            # Build screen context dict if available
            screen_context_dict = None
            if context.has_screen and context.screen_snapshot:
                screen_context_dict = {
                    "active_window": context.screen_snapshot.active_window,
                    "has_image": context.screen_snapshot.image_bytes is not None,
                    "element_count": len(context.screen_snapshot.elements),
                }

            response = self._orchestrator.process_input(
                text=context.get_primary_text(),
                source=context.source,
                screen_context=screen_context_dict,
            )
            
            # Update state to idle
            self._update_state(AgentState.IDLE)
            
            # Send response callback
            if self._on_response:
                self._on_response(response.formatted_message)
            
            # Memory feedback loop is handled by orchestrator internally
            # through MemoryManager integration
            
        except Exception as e:
            logger.error_data("Orchestrator error", {"error": str(e)})
            self._update_state(AgentState.ERROR)
    
    def _build_context(self, event: LoopEvent) -> UnifiedInputContext:
        """Build unified input context from event."""
        if event.event_type == LoopEventType.TEXT_INPUT:
            text = event.data.get("text", "") if event.data else ""
            return UnifiedInputContext.from_text(text)
        
        elif event.event_type == LoopEventType.VOICE_INPUT:
            # Check if text is already transcribed (from wake word)
            if event.data and "text" in event.data:
                text = event.data.get("text", "")
                confidence = event.data.get("confidence", 0.0)
                return UnifiedInputContext(voice_text=text, voice_confidence=confidence, source="voice")
            # Otherwise, transcribe audio
            audio = event.data.get("audio") if event.data else None
            if audio and self._voice_input:
                voice_event = self._voice_input.transcribe(audio)
                return UnifiedInputContext.from_voice(voice_event)
            return UnifiedInputContext()
        
        elif event.event_type == LoopEventType.WAKE_WORD:
            # Wake word detected without audio, just log
            logger.info("Wake word detected (no audio)")
            return UnifiedInputContext()
        
        elif event.event_type == LoopEventType.SCREEN_CAPTURE:
            if self._screen_input and self._screen_input.is_available():
                snapshot = self._screen_input.capture()
                return UnifiedInputContext.from_screen(snapshot)
            return UnifiedInputContext()
        
        return UnifiedInputContext()
    
    def _on_wake_word(self, event: WakeWordEvent) -> None:
        """Handle wake word detection - automatically trigger voice capture."""
        logger.info_data("Wake word detected", {"word": event.word})
        
        # If audio data is provided, transcribe it directly
        if event.audio_data and self._voice_input:
            voice_event = self._voice_input.transcribe(event.audio_data)
            if voice_event.text:
                # Submit voice transcription to loop
                loop_event = LoopEvent(
                    LoopEventType.VOICE_INPUT,
                    data={"text": voice_event.text, "confidence": voice_event.confidence}
                )
                self._event_queue.put(loop_event)
                return
        
        # Otherwise, submit wake word event to trigger manual voice capture
        loop_event = LoopEvent(
            LoopEventType.WAKE_WORD,
            data={"word": event.word}
        )
        self._event_queue.put(loop_event)
    
    def _update_state(self, state: AgentState) -> None:
        """Update agent state and notify callback."""
        if self._on_state_change:
            self._on_state_change(state)
    
    def is_running(self) -> bool:
        """Check if loop is running."""
        return self._running
    
    def is_paused(self) -> bool:
        """Check if loop is paused."""
        return self._paused
