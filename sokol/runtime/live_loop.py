"""Live loop controller for continuous agent operation."""

import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from sokol.runtime.unified_input import UnifiedInputContext
from sokol.runtime.orchestrator import Orchestrator
from sokol.runtime.backpressure import BackpressureLayer
from sokol.runtime.priority import PriorityPolicy, EventPriority
from sokol.runtime.metrics import MetricsCollector
from sokol.runtime.health import HealthChecker
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
    metadata: Optional[dict] = None  # V2: Add metadata for priority, etc.


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
        self._on_event_drop: Optional[Callable[[str, str], None]] = None  # P0: Event drop notification
        
        # V2: Backpressure layer
        self._backpressure = BackpressureLayer(self._event_queue, maxsize=100)
        
        # V2: Priority policy
        self._priority_policy = PriorityPolicy()
        
        # V2: Metrics collector
        self._metrics = MetricsCollector(max_history=1000)
        
        # V2: Health checker
        self._health = HealthChecker()
        
        # V2: Track per-source throttling
        self._source_last_accept: dict[str, float] = {}
        
        # V2: Track event processing times
        self._event_start_times: dict[str, float] = {}
        
        # V2: Register health checks
        self._health.register_check("queue_not_full", self._check_queue_health)
        self._health.register_check("loop_running", self._check_loop_health)
        
        logger.info("Live loop controller initialized (V2 with backpressure, priority, metrics)")
    
    def set_state_change_callback(self, callback: Callable[[AgentState], None]) -> None:
        """Set callback for agent state changes."""
        self._on_state_change = callback
    
    def set_response_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for agent responses."""
        self._on_response = callback
    
    def set_event_drop_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Set callback for event drop notifications.
        
        Args:
            callback: Function called with (source, reason) when event is dropped
        """
        self._on_event_drop = callback
    
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
    
    def submit_text(self, text: str, source: str = "user") -> bool:
        """Submit text input to the loop with V2 backpressure and priority.
        
        Args:
            text: Text input
            source: Input source identifier
        
        Returns:
            True if accepted, False if throttled/dropped
        """
        event = LoopEvent(
            LoopEventType.TEXT_INPUT,
            data={"text": text},
            metadata={"source": source}
        )
        
        # V2: Assign priority
        priority = self._priority_policy.assign_priority(event.event_type.value, event.data)
        pressure = self._backpressure.get_pressure_level()
        
        # V2: Check drop policy
        should_drop, drop_reason = self._priority_policy.should_drop_under_pressure(priority, pressure)
        if should_drop:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": drop_reason}
            )
            logger.warning_data("Event dropped by priority policy",
                {"source": source, "reason": drop_reason, "priority": priority})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, drop_reason)
            return False
        
        # V2: Check backpressure admission
        accept, accept_reason = self._backpressure.should_accept_event(priority)
        if not accept:
            self._metrics.increment_counter(
                "events_throttled_total",
                tags={"source": source, "reason": accept_reason}
            )
            logger.warning_data("Event throttled by backpressure",
                {"source": source, "reason": accept_reason})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, accept_reason)
            return False
        
        # V2: Check adaptive throttling delay
        throttle_delay = self._backpressure.get_throttle_delay_ms(source)
        if throttle_delay > 0:
            last_accept = self._source_last_accept.get(source, 0)
            elapsed_ms = (time.time() - last_accept) * 1000
            
            if elapsed_ms < throttle_delay:
                self._metrics.increment_counter(
                    "events_throttled_total",
                    tags={"source": source, "reason": "adaptive_delay"}
                )
                logger.debug_data("Event throttled by adaptive delay",
                    {"source": source, "delay_ms": throttle_delay})
                # P0: Notify callback
                if self._on_event_drop:
                    self._on_event_drop(source, "adaptive_delay")
                return False
        
        # Submit to queue
        try:
            self._event_queue.put_nowait(event)
            self._source_last_accept[source] = time.time()
            self._metrics.increment_counter(
                "events_submitted_total",
                tags={"source": source}
            )
            logger.debug(f"Text input submitted: {text[:50]}...")
            return True
        except queue.Full:
            self._queue_drop_count += 1
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": "queue_full"}
            )
            logger.warning_data("Text event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, "queue_full")
            return False
    
    def submit_voice(self, audio_data: bytes, source: str = "voice") -> bool:
        """Submit voice audio to the loop with V2 backpressure and priority.
        
        Args:
            audio_data: Audio data
            source: Input source identifier
        
        Returns:
            True if accepted, False if throttled/dropped
        """
        event = LoopEvent(
            LoopEventType.VOICE_INPUT,
            data={"audio": audio_data},
            metadata={"source": source}
        )
        
        # V2: Assign priority and check policies
        priority = self._priority_policy.assign_priority(event.event_type.value, event.data)
        pressure = self._backpressure.get_pressure_level()
        
        should_drop, drop_reason = self._priority_policy.should_drop_under_pressure(priority, pressure)
        if should_drop:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": drop_reason}
            )
            logger.warning_data("Voice event dropped by priority policy",
                {"source": source, "reason": drop_reason})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, drop_reason)
            return False
        
        accept, accept_reason = self._backpressure.should_accept_event(priority)
        if not accept:
            self._metrics.increment_counter(
                "events_throttled_total",
                tags={"source": source, "reason": accept_reason}
            )
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, accept_reason)
            return False
        
        try:
            self._event_queue.put_nowait(event)
            self._metrics.increment_counter(
                "events_submitted_total",
                tags={"source": source}
            )
            logger.debug("Voice input submitted")
            return True
        except queue.Full:
            self._queue_drop_count += 1
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": "queue_full"}
            )
            logger.warning_data("Voice event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, "queue_full")
            return False
    
    def request_screen_capture(self, source: str = "screen") -> bool:
        """Request screen capture in the next cycle with V2 backpressure and priority.
        
        Args:
            source: Input source identifier
        
        Returns:
            True if accepted, False if throttled/dropped
        """
        event = LoopEvent(
            LoopEventType.SCREEN_CAPTURE,
            metadata={"source": source}
        )
        
        # V2: Assign priority and check policies
        priority = self._priority_policy.assign_priority(event.event_type.value, event.data)
        pressure = self._backpressure.get_pressure_level()
        
        should_drop, drop_reason = self._priority_policy.should_drop_under_pressure(priority, pressure)
        if should_drop:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": drop_reason}
            )
            logger.warning_data("Screen capture dropped by priority policy",
                {"source": source, "reason": drop_reason})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, drop_reason)
            return False
        
        accept, accept_reason = self._backpressure.should_accept_event(priority)
        if not accept:
            self._metrics.increment_counter(
                "events_throttled_total",
                tags={"source": source, "reason": accept_reason}
            )
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, accept_reason)
            return False
        
        try:
            self._event_queue.put_nowait(event)
            self._metrics.increment_counter(
                "events_submitted_total",
                tags={"source": source}
            )
            logger.debug("Screen capture requested")
            return True
        except queue.Full:
            self._queue_drop_count += 1
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": "queue_full"}
            )
            logger.warning_data("Screen capture event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, "queue_full")
            return False
    
    def _loop_main(self) -> None:
        """Main loop thread with V2 metrics tracking."""
        logger.info("Live loop thread started")
        
        while self._running:
            try:
                # V2: Track queue depth and pressure
                queue_depth = self._event_queue.qsize()
                self._metrics.set_gauge("queue_depth", queue_depth)
                
                pressure = self._backpressure.get_pressure_level()
                self._metrics.set_gauge("queue_pressure", 
                    {"low": 0, "medium": 1, "high": 2, "critical": 3}[pressure]
                )
                
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
                        self._metrics.increment_counter(
                            "events_dropped_total",
                            tags={"reason": "paused_buffer_full"}
                        )
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
                if queue_depth > 50:
                    logger.warning_data("Event queue near capacity",
                        {"queue_size": queue_depth, "maxsize": 100, "drops": self._queue_drop_count})
                elif queue_depth > 10:
                    logger.warning_data("Event queue backing up", {"queue_size": queue_depth})
                
            except Exception as e:
                self._metrics.increment_counter(
                    "loop_errors_total",
                    tags={"error_type": type(e).__name__}
                )
                logger.error_data("Loop error", {"error": str(e), "traceback": str(e.__traceback__)})
                # Continue loop despite errors
        
        logger.info("Live loop thread stopped")
    
    def _process_event(self, event: LoopEvent) -> None:
        """Process a single event with V2 metrics tracking."""
        # V2: Track event start time
        event_id = f"{event.event_type.value}_{time.time()}"
        self._event_start_times[event_id] = time.time()
        
        # Update state to thinking
        self._update_state(AgentState.THINKING)
        
        # Build unified input context
        context = self._build_context(event)
        
        if context.is_empty():
            logger.warning("Empty context, skipping")
            self._metrics.increment_counter(
                "events_skipped_total",
                tags={"reason": "empty_context"}
            )
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
            
            # V2: Track successful processing
            self._metrics.increment_counter(
                "events_processed_total",
                tags={"type": event.event_type.value}
            )
            
            # Memory feedback loop is handled by orchestrator internally
            # through MemoryManager integration
            
        except Exception as e:
            self._metrics.increment_counter(
                "events_failed_total",
                tags={"type": event.event_type.value, "error": type(e).__name__}
            )
            logger.error_data("Orchestrator error", {"error": str(e)})
            self._update_state(AgentState.ERROR)
        finally:
            # V2: Track event latency
            if event_id in self._event_start_times:
                latency_ms = (time.time() - self._event_start_times[event_id]) * 1000
                self._metrics.observe_histogram(
                    "event_latency_ms",
                    latency_ms,
                    tags={"type": event.event_type.value}
                )
                del self._event_start_times[event_id]
    
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
        """Handle wake word detection - automatically trigger voice capture with V2."""
        logger.info_data("Wake word detected", {"word": event.word})
        self._metrics.increment_counter(
            "wake_word_detected_total",
            tags={"word": event.word}
        )
        
        # If audio data is provided, transcribe it directly
        if event.audio_data and self._voice_input:
            voice_event = self._voice_input.transcribe(event.audio_data)
            if voice_event.text:
                # Submit voice transcription to loop via V2 method
                self.submit_voice(
                    audio_data=event.audio_data,
                    source="wake_word"
                )
                return
        
        # Otherwise, submit wake word event to trigger manual voice capture
        loop_event = LoopEvent(
            LoopEventType.WAKE_WORD,
            data={"word": event.word},
            metadata={"source": "wake_word"}
        )
        
        # V2: Use priority policy
        priority = self._priority_policy.assign_priority(loop_event.event_type.value, loop_event.data)
        pressure = self._backpressure.get_pressure_level()
        
        should_drop, drop_reason = self._priority_policy.should_drop_under_pressure(priority, pressure)
        if should_drop:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": "wake_word", "reason": drop_reason}
            )
            logger.warning_data("Wake word event dropped by priority policy",
                {"reason": drop_reason})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop("wake_word", drop_reason)
            return
        
        try:
            self._event_queue.put_nowait(loop_event)
            self._metrics.increment_counter(
                "events_submitted_total",
                tags={"source": "wake_word"}
            )
        except queue.Full:
            self._queue_drop_count += 1
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": "wake_word", "reason": "queue_full"}
            )
            logger.warning_data("Wake word event dropped - queue full",
                {"queue_size": 100, "drop_count": self._queue_drop_count})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop("wake_word", "queue_full")
    
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
    
    def _check_queue_health(self) -> bool:
        """V2: Check if queue is healthy."""
        return self._event_queue.qsize() < self._event_queue.maxsize * 0.9
    
    def _check_loop_health(self) -> bool:
        """V2: Check if loop is running."""
        return self._running and not self._paused
    
    def get_health_status(self) -> dict:
        """V2: Get health status."""
        return self._health.get_health_status()
    
    def get_metrics(self) -> dict:
        """V2: Get all metrics."""
        return self._metrics.get_all_metrics()
    
    def export_prometheus_metrics(self) -> str:
        """V2: Export metrics in Prometheus format."""
        return self._metrics.export_prometheus()
    
    def get_queue_pressure(self) -> str:
        """V2: Get current queue pressure level."""
        return self._backpressure.get_pressure_level()
    
    def get_queue_fill_ratio(self) -> float:
        """V2: Get queue fill ratio."""
        return self._backpressure.get_fill_ratio()
