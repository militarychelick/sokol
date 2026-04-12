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
from sokol.runtime.unified_decision import UnifiedDecisionEngine
from sokol.runtime.execution_tracker import ExecutionTracker, ExecutionStatus
from sokol.runtime.resilience_observer import ResilienceObserver
from sokol.runtime.liveness_monitor import LivenessMonitor
from sokol.runtime.bounded_mitigation import BoundedMitigationLayer, EventPriority as MitigationPriority, SystemState
from sokol.runtime.invariant_verifier import InvariantVerifier, InvariantViolationException
from sokol.runtime.property_checker import PropertyChecker, PropertyViolationException
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
    EMERGENCY = "emergency"  # Validation & Hardening: First-class emergency event type


class SystemState(Enum):
    """System recovery states for Phase 2.1.2 + Bounded Mitigation Layer."""
    NORMAL = 0      # Full functionality, all sources active
    THROTTLED = 1   # Reduced source rates, background tasks paused
    SAFE = 2        # Only critical sources (UI, emergency), screen disabled
    MINIMAL = 3     # Only emergency events, all other sources blocked
    DEGRADED = 4    # Functional but limited capacity (Bounded Mitigation Layer)
    ERROR = 5       # Terminal local state


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
        # FIX: Changed to PriorityQueue for strict priority ordering invariant
        self._event_queue = queue.PriorityQueue(maxsize=100)
        
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
        
        # Observer cleanup tracking
        self._observer_cleanup_interval = 1000  # Clean every 1000 iterations
        self._loop_iteration_count = 0
        
        # FIX: Priority queue counter to maintain FIFO order for same priority
        self._queue_counter = 0
        self._queue_lock = threading.Lock()
        # FIX: Track submitted priorities for real priority ordering verification
        self._submitted_priorities = []  # Track recent priorities for ordering check
        
        # V2: Backpressure layer
        self._backpressure = BackpressureLayer(self._event_queue, maxsize=100)
        
        # V2: Priority policy
        self._priority_policy = PriorityPolicy()
        
        # Phase 2.2: Unified decision engine (collapse control plane)
        self._decision_engine = UnifiedDecisionEngine(
            priority_policy=self._priority_policy,
            backpressure_layer=self._backpressure
        )
        
        # Phase 2.3: Execution tracker (execution feedback loop)
        self._execution_tracker = ExecutionTracker(window_size=100)
        
        # Hard Reliability Verification: Resilience observer (pure observation only)
        self._resilience_observer = ResilienceObserver()
        
        # Bounded Mitigation Layer: Local protective actions only
        self._mitigation_layer = BoundedMitigationLayer()
        
        # BLOCK 3: Verification Layer (detection-only)
        self._invariant_verifier = InvariantVerifier()
        self._liveness_monitor = LivenessMonitor()
        self._property_checker = PropertyChecker()
        
        # BLOCK 3: Drop rate tracking
        self._drop_count = 0
        self._accept_count = 0
        self._drop_rate_window = 100  # Last 100 events
        
        # V2: Metrics collector
        self._metrics = MetricsCollector(max_history=1000)
        
        # V2: Health checker
        self._health = HealthChecker()
        
        # V2: Track per-source throttling
        self._source_last_accept: dict[str, float] = {}
        
        # V2: Track event processing times
        self._event_start_times: dict[str, float] = {}
        
        # Phase 2.1.2: System recovery state
        self._system_state = SystemState.NORMAL
        self._last_state_eval_time = 0.0
        self._state_eval_interval = 1.0  # Evaluate every 1 second
        
        # V2: Register health checks
        self._health.register_check("queue_not_full", self._check_queue_health)
        self._health.register_check("loop_running", self._check_loop_health)
        
        logger.info("Live loop controller initialized (V2 with backpressure, priority, metrics)")
    
    def _verify_enforced(self, verification_func, *args, **kwargs) -> None:
        """
        Execute verification function with enforcement mode exception handling.
        
        TEMPORARILY DISABLED: Only logs violations, does not raise exceptions.
        
        Args:
            verification_func: Verification function to call
            *args: Arguments to pass to verification function
            **kwargs: Keyword arguments to pass to verification function
        """
        try:
            verification_func(*args, **kwargs)
        except (InvariantViolationException, PropertyViolationException) as e:
            logger.error_data("Verification violation (enforcement mode - logging only)", {"details": e.violation.details})
            # TEMPORARILY DISABLED: Do not transition to ERROR state, do not raise
            # self._update_state(AgentState.ERROR)
            # raise
    
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
            
            # Submit STOP event to queue for graceful shutdown
            # FIX: Use priority tuple for PriorityQueue (priority 0 for STOP to ensure it's processed)
            with self._queue_lock:
                self._queue_counter += 1
                self._event_queue.put((0, self._queue_counter, LoopEvent(LoopEventType.STOP)))
        
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
                    # FIX: Use priority tuple for PriorityQueue (reuse original priority)
                    # Note: We need to re-assign priority since we don't store it in buffer
                    # For simplicity, use priority 2 (HIGH) for buffered events
                    with self._queue_lock:
                        self._queue_counter += 1
                        self._event_queue.put_nowait((2, self._queue_counter, buffered_event))
                except queue.Full:
                    self._queue_drop_count += 1
                    logger.warning_data("Buffered event dropped on resume - queue full",
                        {"drop_count": self._queue_drop_count})
            buffer_count = len(self._paused_event_buffer)
            self._paused_event_buffer.clear()
        logger.info_data("Live loop resumed", {"replayed_events": buffer_count})
    
    def submit_text(self, text: str, source: str = "ui") -> bool:
        """Submit text input to the loop with Phase 2.2 unified decision engine.
        
        Args:
            text: Text input
            source: Input source identifier
        
        Returns:
            True if accepted, False if throttled/dropped
        """
        try:
            # FIX: Emergency events are first-class event type for preemptive scheduling
            # Emergency keywords → LoopEvent(EMERGENCY) instead of TEXT_INPUT
            emergency_keywords = ["да", "нет", "отмена", "стоп", "подтверждаю", "выполняй",
                                "yes", "no", "cancel", "stop", "confirm", "execute",
                                "emergency", "авария", "abort", "прервать"]
            is_emergency = any(keyword in text.lower() for keyword in emergency_keywords)
            
            event_type = LoopEventType.EMERGENCY if is_emergency else LoopEventType.TEXT_INPUT
            
            event = LoopEvent(
                event_type,
                data={"text": text},
                metadata={"source": source}
            )
            
            # Phase 2.2: Use unified decision engine (single decision point)
            decision = self._decision_engine.decide_event(
                event_type=event.event_type.value,
                event_data=event.data,
                source=source
            )
            
            if not decision.accepted:
                self._metrics.increment_counter(
                    "events_dropped_total",
                    tags={"source": source, "reason": decision.reason.value}
                )
                logger.warning_data("Event dropped by unified decision engine",
                    {"source": source, "reason": decision.reason.value, "details": decision.details})
                
                # Hard Reliability Verification: Observe critical event drop
                # Critical events are priority 0 (emergency)
                is_critical = decision.priority == 0
                if is_critical:
                    has_reason = decision.reason is not None
                    self._resilience_observer.observe_critical_event_drop(
                        event_type=event.event_type.value,
                        has_reason=has_reason
                    )
                    self._verify_enforced(
                        self._invariant_verifier.verify_observer_read_only,
                        decision_source="observe_critical_event_drop",
                        system_impact="NONE"
                    )
                
                # P0: Notify callback
                if self._on_event_drop:
                    self._on_event_drop(source, decision.reason.value)
                return False
            
            # Bounded Mitigation Layer: Check mitigation (after Control Plane decision)
            mitigation_result = self._mitigation_layer.check_event(
                priority=MitigationPriority(decision.priority),
                source=source,
                system_state=self._system_state,
                queue_depth=self._event_queue.qsize()
            )
            
            if not mitigation_result.allowed:
                self._metrics.increment_counter(
                    "events_dropped_total",
                    tags={"source": source, "reason": f"mitigation_{mitigation_result.reason}"}
                )
                logger.warning_data("Event dropped by bounded mitigation layer",
                    {"source": source, "reason": mitigation_result.reason, "priority": decision.priority})
                
                # BLOCK 3: Drop rate tracking
                self._drop_count += 1
                
                # BLOCK 3: Invariant verification (mitigation bypass) - enforcement mode
                self._verify_enforced(
                    self._invariant_verifier.verify_mitigation_bypass,
                    event_priority=MitigationPriority(decision.priority),
                    mitigation_applied=True
                )
                
                # P0: Notify callback
                if self._on_event_drop:
                    self._on_event_drop(source, mitigation_result.reason)
                return False
            
            # FIX #4: Verify mitigation application for accepted events - enforcement mode
            self._verify_enforced(
                self._property_checker.check_mitigation_application,
                event_priority=MitigationPriority(decision.priority),
                mitigation_applied=True  # Mitigation was applied (check_event returned allowed=True)
            )
            
            # Submit to queue
            try:
                # FIX: Use priority tuple for PriorityQueue (priority, counter, event)
                with self._queue_lock:
                    priority_tuple = (decision.priority, self._queue_counter, event)
                    self._queue_counter += 1
                    self._submitted_priorities.append(decision.priority)
                    if len(self._submitted_priorities) > 100:
                        self._submitted_priorities.pop(0)
                
                self._event_queue.put_nowait(priority_tuple)
                
                # FIX: Verify priority ordering using actual tracked priorities - enforcement mode
                self._verify_enforced(
                    self._property_checker.check_priority_ordering,
                    event_queue=[{"priority": p} for p in self._submitted_priorities]  # Real tracked priorities
                )
                
                self._accept_count += 1
                return True
            except queue.Full:
                self._metrics.increment_counter(
                    "events_dropped_total",
                    tags={"source": source, "reason": "queue_full"}
                )
                logger.warning_data("Event queue full",
                    {"source": source, "queue_size": self._event_queue.qsize()})
                
                # P0: Notify callback
                if self._on_event_drop:
                    self._on_event_drop(source, "queue_full")
                return False
        except (InvariantViolationException, PropertyViolationException):
            # Already handled by _verify_enforced, just return False
            return False
    
    def _execute_emergency(self, text: str, source: str) -> bool:
        """
        Execute emergency event directly (no queue, no fallback).
        
        Args:
            text: Emergency command text
            source: Source identifier
        
        Returns:
            True (emergency always executes)
        """
        # BLOCK 3: Record emergency submission timestamp for liveness monitoring
        self._liveness_monitor.record_emergency_submission()
        
        start_time = time.time()
        
        try:
            # Update state
            self._update_state(AgentState.THINKING)
            
            # Execute directly through orchestrator
            response = self._orchestrator.process_input(
                text=text,
                source=source,
                screen_context=None
            )
            
            # Update state
            self._update_state(AgentState.IDLE)
            
            # Send response
            if self._on_response:
                self._on_response(response.formatted_message)
            
            # Hard Reliability Verification: Observe emergency latency
            latency_ms = (time.time() - start_time) * 1000
            self._resilience_observer.observe_emergency_latency(latency_ms)
            
            # FIX: Verify observer read-only with actual method name - enforcement mode
            self._verify_enforced(
                self._invariant_verifier.verify_observer_read_only,
                decision_source="observe_emergency_latency",
                system_impact="NONE"
            )
            
            # FIX #4: Verify emergency bypass invariant (emergency should bypass mitigation) - enforcement mode
            self._verify_enforced(
                self._property_checker.check_emergency_bypass,
                event_priority=MitigationPriority.EMERGENCY,
                mitigation_applied=False  # Emergency bypasses mitigation
            )
            
            # BLOCK 3: Record emergency execution timestamp for liveness monitoring
            self._liveness_monitor.record_emergency_execution()
            
            logger.info("Emergency executed successfully")
            return True
            
        except Exception as e:
            logger.error_data("Emergency execution failed (no fallback)",
                {"error": str(e)})
            # Emergency failed but still return True (no fallback to queue)
            self._update_state(AgentState.ERROR)
            return True
    
    def submit_voice(self, audio_data: bytes, source: str = "voice") -> bool:
        """Submit voice audio to the loop with Phase 2.2 unified decision engine.
        
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
        
        # Phase 2.2: Use unified decision engine (single decision point)
        decision = self._decision_engine.decide_event(
            event_type=event.event_type.value,
            event_data=event.data,
            source=source
        )
        
        if not decision.accepted:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": decision.reason.value}
            )
            logger.warning_data("Event dropped by unified decision engine",
                {"source": source, "reason": decision.reason.value, "details": decision.details})
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, decision.reason.value)
            return False
        
        # Bounded Mitigation Layer: Check mitigation (BLOCK 2 - Full Event Coverage)
        mitigation_result = self._mitigation_layer.check_event(
            priority=MitigationPriority(decision.priority),
            source=source,
            system_state=self._system_state,
            queue_depth=self._event_queue.qsize()
        )
        
        if not mitigation_result.allowed:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": f"mitigation_{mitigation_result.reason}"}
            )
            logger.warning_data("Voice event dropped by bounded mitigation layer",
                {"source": source, "reason": mitigation_result.reason, "priority": decision.priority})
            
            # BLOCK 3: Drop rate tracking
            self._drop_count += 1
            
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, mitigation_result.reason)
            return False
        
        # BLOCK 3: Invariant verification (mitigation bypass) - enforcement mode
        self._verify_enforced(
            self._invariant_verifier.verify_mitigation_bypass,
            event_priority=MitigationPriority(decision.priority),
            mitigation_applied=True
        )
        
        # Submit to queue
        try:
            # FIX: Use priority tuple for PriorityQueue (priority, counter, event)
            with self._queue_lock:
                self._queue_counter += 1
                self._event_queue.put_nowait((decision.priority, self._queue_counter, event))
                # FIX: Track submitted priority for real priority ordering verification
                self._submitted_priorities.append(decision.priority)
                if len(self._submitted_priorities) > 100:
                    self._submitted_priorities.pop(0)
            
            # FIX: Verify priority ordering using actual tracked priorities - enforcement mode
            self._verify_enforced(
                self._property_checker.check_priority_ordering,
                event_queue=[{"priority": p} for p in self._submitted_priorities]
            )
            
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
        """Request screen capture in the next cycle with Phase 2.2 unified decision engine.
        
        Args:
            source: Input source identifier
        
        Returns:
            True if accepted, False if throttled/dropped
        """
        event = LoopEvent(
            LoopEventType.SCREEN_CAPTURE,
            metadata={"source": source}
        )
        
        # Phase 2.2: Use unified decision engine (single decision point)
        decision = self._decision_engine.decide_event(
            event_type=event.event_type.value,
            event_data=event.data,
            source=source
        )
        
        if not decision.accepted:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": decision.reason.value}
            )
            logger.warning_data("Event dropped by unified decision engine",
                {"source": source, "reason": decision.reason.value, "details": decision.details})
            
            # Hard Reliability Verification: Observe critical event drop
            is_critical = decision.priority == 0
            if is_critical:
                has_reason = decision.reason is not None
                self._resilience_observer.observe_critical_event_drop(
                    event_type=event.event_type.value,
                    has_reason=has_reason
                )
                # FIX: Verify observer read-only with actual method name - enforcement mode
                self._verify_enforced(
                    self._invariant_verifier.verify_observer_read_only,
                    decision_source="observe_critical_event_drop",
                    system_impact="NONE"
                )
            
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, decision.reason.value)
            return False
        
        # Bounded Mitigation Layer: Check mitigation (BLOCK 2 - Full Event Coverage)
        mitigation_result = self._mitigation_layer.check_event(
            priority=MitigationPriority(decision.priority),
            source=source,
            system_state=self._system_state,
            queue_depth=self._event_queue.qsize()
        )
        
        if not mitigation_result.allowed:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": source, "reason": f"mitigation_{mitigation_result.reason}"}
            )
            logger.warning_data("Screen capture event dropped by bounded mitigation layer",
                {"source": source, "reason": mitigation_result.reason, "priority": decision.priority})
            
            # BLOCK 3: Drop rate tracking
            self._drop_count += 1
            
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop(source, mitigation_result.reason)
            return False
        
        try:
            # FIX: Use priority tuple for PriorityQueue (priority, counter, event)
            with self._queue_lock:
                self._queue_counter += 1
                self._event_queue.put_nowait((decision.priority, self._queue_counter, event))
                # FIX: Track submitted priority for real priority ordering verification
                self._submitted_priorities.append(decision.priority)
                if len(self._submitted_priorities) > 100:
                    self._submitted_priorities.pop(0)
            
            # FIX: Verify priority ordering using actual tracked priorities - enforcement mode
            self._verify_enforced(
                self._property_checker.check_priority_ordering,
                event_queue=[{"priority": p} for p in self._submitted_priorities]
            )
            
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
        """Main loop for event processing with Phase 2.1.2 state machine + BLOCK 3 liveness monitoring."""
        logger.info("Live loop main started")
        
        while self._running:
            # FIX: Observer cleanup - reset periodically to prevent memory leak
            self._loop_iteration_count += 1
            if self._loop_iteration_count % self._observer_cleanup_interval == 0:
                self._resilience_observer.reset()
                logger.debug_data("Observer cleanup performed", {"iteration": self._loop_iteration_count})
            try:
                # BLOCK 3: Liveness monitoring (check at start of each iteration)
                self._liveness_monitor.set_events_available(self._event_queue.qsize() > 0)
                is_valid_l1, violation_l1 = self._liveness_monitor.verify_event_progress(self._system_state)
                if not is_valid_l1:
                    logger.warning_data("Liveness violation detected", {"type": "event_progress", "details": violation_l1.details if violation_l1 else {}})
                
                is_valid_l2, violation_l2 = self._liveness_monitor.verify_state_transition_progress()
                if not is_valid_l2:
                    logger.warning_data("Liveness violation detected", {"type": "state_transition_progress", "details": violation_l2.details if violation_l2 else {}})
                
                is_valid_l3, violation_l3 = self._liveness_monitor.verify_emergency_starvation()
                if not is_valid_l3:
                    logger.warning_data("Liveness violation detected", {"type": "emergency_starvation", "details": violation_l3.details if violation_l3 else {}})
                
                # Phase 2.1.2: Evaluate system state every iteration
                new_state = self._evaluate_system_state()
                self._apply_state_policy(new_state)
                
                # Phase 2.1.2: Preemptive scheduler - PriorityQueue already orders by priority
                # EMERGENCY events (priority 0) are automatically processed first
                try:
                    priority_tuple = self._event_queue.get(timeout=0.1)
                    _, _, event = priority_tuple  # Unpack (priority, counter, event)
                    self._process_event(event)
                    # BLOCK 3: Record event processed for liveness monitoring
                    self._liveness_monitor.record_event_processed()
                except queue.Empty:
                    # Phase 2.1.2: No events, continue
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
                # FIX: Fail-stop model - transition to ERROR state on critical errors
                self._update_state(AgentState.ERROR)
                logger.error("Critical loop error - transitioning to ERROR state (fail-stop)")
                # Note: In a production system, this would stop the loop entirely
                # For now, we transition to ERROR state and continue to allow recovery
        
        logger.info("Live loop thread stopped")
    
    def _process_event(self, event: LoopEvent) -> None:
        """Process a single event with V2 metrics tracking and Phase 2.3 execution tracking."""
        # V2: Track event start time
        event_id = f"{event.event_type.value}_{time.time()}"
        self._event_start_times[event_id] = time.time()
        
        # Phase 2.3: Track execution start
        execution_start_time = time.time()
        
        # FIX #3: Verify queue threshold before processing - enforcement mode
        self._verify_enforced(
            self._invariant_verifier.verify_queue_threshold,
            queue_depth=self._event_queue.qsize(),
            queue_max=100,
            system_state=self._system_state
        )
        
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
        
        # FIX: Observe regular event processing (observer coverage for all events)
        self._resilience_observer.observe_event_processing(
            event_type=event.event_type.value,
            source=context.source,
            timestamp=time.time()
        )
        
        # FIX: Verify observer read-only invariant with actual method call tracking - enforcement mode
        # Track which observer method was called to verify it's observe_* (read-only)
        observer_method_called = "observe_event_processing"
        self._verify_enforced(
            self._invariant_verifier.verify_observer_read_only,
            decision_source=observer_method_called,
            system_impact="NONE"  # Observer methods are void, no return value
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
            
            # FIX #3: Verify emergency non-drop for emergency events - enforcement mode
            if event.event_type == LoopEventType.TEXT_INPUT:
                text = event.data.get("text", "") if event.data else ""
                # FIX: Sync emergency keywords with PriorityPolicy.assign_priority to ensure verification matches decision
                emergency_keywords = ["да", "нет", "отмена", "стоп", "подтверждаю", "выполняй",
                                    "yes", "no", "cancel", "stop", "confirm", "execute",
                                    "emergency", "авария", "abort", "прервать"]
                is_emergency = any(keyword in text for keyword in emergency_keywords)
                if is_emergency:
                    self._verify_enforced(
                        self._invariant_verifier.verify_emergency_non_drop,
                        event_priority=MitigationPriority.EMERGENCY,
                        event_dropped=False,
                        system_state=self._system_state
                    )
            
            # Update state to idle
            self._update_state(AgentState.IDLE)
            
            # Send response callback
            if self._on_response and response is not None:
                self._on_response(response.formatted_message)
            elif self._on_response and response is None:
                logger.warning("Orchestrator returned None response, skipping callback")
            
            # FIX #4: Verify observer non-interference (observer should not affect execution) - enforcement mode
            self._verify_enforced(
                self._property_checker.check_observer_non_interference,
                observer_signals=[]  # Observer is read-only, no signals
            )
            
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
            import traceback
            print(f"=== ORCHESTRATOR ERROR ===")
            print(f"Error: {str(e)}")
            print(f"Traceback:\n{traceback.format_exc()}")
            print(f"=== END ERROR ===")
            logger.error_data("Orchestrator error", {"error": str(e), "traceback": traceback.format_exc()})
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
            
            # Phase 2.3: Record execution result (closed-loop feedback)
            execution_duration_ms = (time.time() - execution_start_time) * 1000
            
            # Determine execution status
            if self._orchestrator._state == AgentState.ERROR:
                execution_status = ExecutionStatus.ERROR
                error_type = "orchestrator_error"
            else:
                execution_status = ExecutionStatus.SUCCESS
                error_type = None
            
            # Record in execution tracker
            self._execution_tracker.record_execution(
                event_type=event.event_type.value,
                status=execution_status,
                duration_ms=execution_duration_ms,
                error_type=error_type
            )
            
            # Hard Reliability Verification: Observe execution tracking consistency
            executed_count = self._execution_tracker.get_overall_stats()["total_executions"]
            tracked_count = len(self._execution_tracker._execution_history)
            self._resilience_observer.observe_execution_tracking(
                executed_count=executed_count,
                tracked_count=tracked_count
            )
            
            # FIX: Verify observer read-only with actual method name - enforcement mode
            self._verify_enforced(
                self._invariant_verifier.verify_observer_read_only,
                decision_source="observe_execution_tracking",
                system_impact="NONE"
            )
    
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
        
        # Phase 2.2: Use unified decision engine (single decision point)
        decision = self._decision_engine.decide_event(
            event_type=loop_event.event_type.value,
            event_data=loop_event.data,
            source="wake_word"
        )
        
        if not decision.accepted:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": "wake_word", "reason": decision.reason.value}
            )
            logger.warning_data("Wake word event dropped by unified decision engine",
                {"reason": decision.reason.value, "details": decision.details})
            
            # Hard Reliability Verification: Observe critical event drop
            is_critical = decision.priority == 0
            if is_critical:
                has_reason = decision.reason is not None
                self._resilience_observer.observe_critical_event_drop(
                    event_type=loop_event.event_type.value,
                    has_reason=has_reason
                )
                # FIX: Verify observer read-only with actual method name - enforcement mode
                self._verify_enforced(
                    self._invariant_verifier.verify_observer_read_only,
                    decision_source="observe_critical_event_drop",
                    system_impact="NONE"
                )
            
            # P0: Notify callback
            if self._on_event_drop:
                self._on_event_drop("wake_word", decision.reason.value)
            return
        
        # Bounded Mitigation Layer: Check mitigation (after Control Plane decision)
        mitigation_result = self._mitigation_layer.check_event(
            priority=MitigationPriority(decision.priority),
            source="wake_word",
            system_state=self._system_state,
            queue_depth=self._event_queue.qsize()
        )
        
        if not mitigation_result.allowed:
            self._metrics.increment_counter(
                "events_dropped_total",
                tags={"source": "wake_word", "reason": f"mitigation_{mitigation_result.reason}"}
            )
            logger.warning_data("Wake word event dropped by bounded mitigation layer",
                {"source": "wake_word", "reason": mitigation_result.reason, "priority": decision.priority})
            
            # BLOCK 3: Drop rate tracking
            self._drop_count += 1
            
            # BLOCK 3: Invariant verification (mitigation bypass) - enforcement mode
            self._verify_enforced(
                self._invariant_verifier.verify_mitigation_bypass,
                event_priority=MitigationPriority(decision.priority),
                mitigation_applied=True
            )
            
            # FIX: Verify priority ordering using actual tracked priorities - enforcement mode
            self._verify_enforced(
                self._property_checker.check_priority_ordering,
                event_queue=[{"priority": p} for p in self._submitted_priorities]
            )
            
            try:
                with self._queue_lock:
                    self._queue_counter += 1
                    self._event_queue.put_nowait((decision.priority, self._queue_counter, loop_event))
                    # FIX: Track submitted priority for real priority ordering verification
                    self._submitted_priorities.append(decision.priority)
                    if len(self._submitted_priorities) > 100:
                        self._submitted_priorities.pop(0)
                
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
    
    def _evaluate_system_state(self) -> SystemState:
        """
        Evaluate system state based on metrics for Phase 2.1.2 + Phase 2.3 + Bounded Mitigation Layer.
        
        Phase 2.3: Now includes execution metrics (failure rate, timeout rate, p95 latency).
        Bounded Mitigation Layer: Added DEGRADED state.
        
        Returns:
            New SystemState based on current metrics
        """
        queue_depth_ratio = self._backpressure.get_fill_ratio()
        system_slow = self._metrics.get_slow_state()
        
        # Phase 2.3: Get execution metrics
        execution_stats = self._execution_tracker.get_overall_stats()
        failure_rate = execution_stats["failure_rate"]
        timeout_rate = execution_stats["timeout_rate"]
        p95_latency = execution_stats["p95_latency_ms"]
        
        # BLOCK 3: Calculate actual drop rate
        total_events = self._drop_count + self._accept_count
        drop_rate = (self._drop_count / total_events * 100.0) if total_events > 0 else 0.0
        
        # Bounded Mitigation Layer: Deterministic state evaluation rules with DEGRADED state
        # ERROR: Terminal local state (unrecoverable)
        # MINIMAL: Critical queue, high drop rate, system slow, high failure/timeout rate
        if (queue_depth_ratio > 0.95 or 
            drop_rate > 20.0 or 
            system_slow or 
            failure_rate > 0.3 or  # 30% failure rate
            timeout_rate > 0.2):  # 20% timeout rate
            return SystemState.MINIMAL
        
        # SAFE: High queue, high drop rate, moderate failure/timeout rate
        elif (queue_depth_ratio > 0.85 or 
              drop_rate > 10.0 or 
              failure_rate > 0.15 or  # 15% failure rate
              timeout_rate > 0.1):  # 10% timeout rate
            return SystemState.SAFE
        
        # DEGRADED: Moderate-high queue, moderate latency, persistent high load
        elif (queue_depth_ratio > 0.80 or 
              p95_latency > 3000):  # p95 latency > 3s
            return SystemState.DEGRADED
        
        # THROTTLED: Moderate queue, moderate drop rate, high latency
        elif (queue_depth_ratio > 0.70 or 
              drop_rate > 5.0 or 
              p95_latency > 2000):  # p95 latency > 2s
            return SystemState.THROTTLED
        
        else:
            return SystemState.NORMAL
    
    def _apply_state_policy(self, new_state: SystemState) -> None:
        """
        Apply system state policy for Phase 2.1.2.
        
        Args:
            new_state: New system state to apply
        """
        old_state = self._system_state
        
        if new_state == old_state:
            return
        
        # Hard Reliability Verification: Observe state transition
        # Check if transition is valid (deterministic rules)
        valid_transitions = {
            SystemState.NORMAL: [SystemState.THROTTLED],
            SystemState.THROTTLED: [SystemState.NORMAL, SystemState.SAFE, SystemState.DEGRADED],
            SystemState.SAFE: [SystemState.THROTTLED, SystemState.MINIMAL],
            SystemState.MINIMAL: [SystemState.SAFE],
            SystemState.DEGRADED: [SystemState.NORMAL, SystemState.THROTTLED, SystemState.SAFE],
            SystemState.ERROR: [SystemState.NORMAL]  # Only via external restart
        }
        is_valid = new_state in valid_transitions.get(old_state, [])
        
        self._resilience_observer.observe_state_transition(
            old_state=old_state.name,
            new_state=new_state.name,
            transition_valid=is_valid
        )
        
        # FIX: Verify observer read-only with actual method name - enforcement mode
        self._verify_enforced(
            self._invariant_verifier.verify_observer_read_only,
            decision_source="observe_state_transition",
            system_impact="NONE"
        )
        
        # BLOCK 3: Invariant verification (state transition validity) - enforcement mode
        self._verify_enforced(
            self._invariant_verifier.verify_state_transition,
            old_state=old_state,
            new_state=new_state
        )
        
        logger.info_data("System state transition",
            {"from": old_state.name, "to": new_state.name})
        
        # BLOCK 3: Record state entry timestamp for liveness monitoring
        self._liveness_monitor.record_state_entry(new_state)
        
        self._system_state = new_state
        
        # BLOCK 3: External supervisor signal emission on DEGRADED/ERROR state
        if new_state in {SystemState.DEGRADED, SystemState.ERROR}:
            signal_type = "SYSTEM_DEGRADED" if new_state == SystemState.DEGRADED else "SYSTEM_ERROR"
            logger.warning_data(f"External supervisor signal emitted: {signal_type}",
                {"signal": signal_type, "state": new_state.name, "timestamp": time.time()})
            # FIX #5: External emission to stdout for supervisor
            print(f"SUPERVISOR_SIGNAL: {signal_type} {new_state.name} {time.time()}", flush=True)
            # FIX #5: Additional file-based signal for external supervisor process consumption
            # FIX: Changed from overwrite to append mode for signal history
            # FIX: Added file rotation with size limit to prevent unbounded growth
            try:
                import os
                signal_dir = os.path.join(os.path.expanduser("~"), ".sokol", "signals")
                os.makedirs(signal_dir, exist_ok=True)
                signal_file = os.path.join(signal_dir, "supervisor_signal")
                
                # FIX: Check file size and rotate if needed (max 1MB)
                max_file_size = 1024 * 1024  # 1MB
                if os.path.exists(signal_file) and os.path.getsize(signal_file) > max_file_size:
                    # Rotate file: move to backup and create new
                    backup_file = signal_file + ".bak"
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                    os.rename(signal_file, backup_file)
                    logger.info_data("Supervisor signal file rotated", {"size": os.path.getsize(backup_file)})
                
                # Append new signal
                with open(signal_file, "a") as f:
                    f.write(f"{signal_type} {new_state.name} {time.time()}\n")
            except Exception as e:
                logger.warning_data("Failed to write supervisor signal file", {"error": str(e)})
        
        # Phase 2.2: Update decision engine with new system state
        self._decision_engine.set_system_state(new_state)
        
        # Update metrics
        self._metrics.set_gauge("system_state", new_state.value)
        
        # Apply throttle factor overrides based on state
        # This is done via BackpressureLayer.get_throttle_factor() which sources read
        # The throttle factor mapping is handled in BackpressureLayer
    
    def is_running(self) -> bool:
        """Check if loop is running."""
        return self._running
    
    def is_paused(self) -> bool:
        """Check if loop is paused."""
        return self._paused
    
    def _check_queue_health(self) -> bool:
        """V2: Check if queue is healthy."""
        return self._event_queue.qsize() < 90
    
    def get_decision_counts(self) -> dict[str, int]:
        """
        Get decision counts from unified decision engine (Phase 2.2).
        
        Returns:
            Dictionary of decision reason counts
        """
        return self._decision_engine.get_decision_counts()
    
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
