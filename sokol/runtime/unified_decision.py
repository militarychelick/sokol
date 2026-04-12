"""Unified decision engine for Phase 2.2 - Collapse Control Plane."""

from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import time


class DecisionReason(Enum):
    """Reasons for event acceptance/rejection."""
    ACCEPT = "accept"
    DEDUP_VOICE_BURST = "dedup_voice_burst"
    DEDUP_UI_DUPLICATE = "dedup_ui_duplicate"
    STATE_DROP_BACKGROUND = "state_drop_background"
    STATE_DROP_SCREEN = "state_drop_screen"
    STATE_DROP_VOICE = "state_drop_voice"
    PRIORITY_DROP = "priority_drop"
    THROTTLE_CRITICAL = "throttle_critical"
    THROTTLE_HIGH = "throttle_high"
    QUEUE_FULL = "queue_full"
    EMERGENCY_ACCEPT = "emergency_accept"


@dataclass
class DecisionResult:
    """Result of unified decision engine."""
    accepted: bool
    reason: DecisionReason
    details: Dict[str, any]
    priority: int = 4  # Default priority (NORMAL)


class UnifiedDecisionEngine:
    """
    Unified decision engine that consolidates all control layers.
    
    Replaces 4 independent control systems (RecoveryLoop, BackpressureLayer, 
    PriorityPolicy, DeduplicationLayer) with a single deterministic decision point.
    
    Decision order (deterministic):
    1. Deduplication check
    2. System state check
    3. Priority check
    4. Throttle factor check
    """
    
    def __init__(self, priority_policy, backpressure_layer):
        """
        Initialize unified decision engine.
        
        Args:
            priority_policy: PriorityPolicy instance
            backpressure_layer: BackpressureLayer instance
        """
        self._priority_policy = priority_policy
        self._backpressure_layer = backpressure_layer
        
        # Deduplication tracking
        self._last_voice_time = 0.0
        self._voice_burst_window = 0.5  # 500ms
        self._last_ui_text = ""
        self._last_ui_time = 0.0
        self._ui_dedup_window = 0.2  # 200ms
        
        # System state tracking
        self._system_state = None  # Will be set externally
        
        # Decision tracking
        self._decision_counts = {reason.value: 0 for reason in DecisionReason}
    
    def set_system_state(self, system_state) -> None:
        """
        Set current system state.
        
        Args:
            system_state: Current SystemState enum value
        """
        self._system_state = system_state
    
    def decide_event(
        self,
        event_type: str,
        event_data: Optional[dict],
        source: str
    ) -> DecisionResult:
        """
        Make unified decision on event acceptance.
        
        This is the single decision point for all events.
        
        Args:
            event_type: Event type string
            event_data: Optional event data
            source: Event source identifier
        
        Returns:
            DecisionResult with acceptance status and reason
        """
        # Step 1: Deduplication check
        dedup_result = self._check_deduplication(event_type, event_data, source)
        if not dedup_result.accepted:
            return dedup_result
        
        # Step 2: Priority assignment
        priority = self._priority_policy.assign_priority(event_type, event_data)
        
        # Step 3: System state check
        state_result = self._check_system_state(priority, source)
        if not state_result.accepted:
            return state_result
        
        # Step 4: Throttle factor check (source-level adaptation)
        throttle_result = self._check_throttle_factor(event_type, source)
        if not throttle_result.accepted:
            return throttle_result
        
        # All checks passed - accept event
        self._decision_counts[DecisionReason.ACCEPT.value] += 1
        return DecisionResult(
            accepted=True,
            reason=DecisionReason.ACCEPT,
            details={
                "priority": priority,
                "source": source,
                "state": self._system_state.name if self._system_state else "unknown"
            },
            priority=priority
        )
    
    def _check_deduplication(
        self,
        event_type: str,
        event_data: Optional[dict],
        source: str
    ) -> DecisionResult:
        """Check event deduplication."""
        current_time = time.time()
        
        # Voice burst collapse
        if event_type == "voice_input" and source == "voice":
            if current_time - self._last_voice_time < self._voice_burst_window:
                self._decision_counts[DecisionReason.DEDUP_VOICE_BURST.value] += 1
                return DecisionResult(
                    accepted=False,
                    reason=DecisionReason.DEDUP_VOICE_BURST,
                    details={"source": source, "time_since_last": current_time - self._last_voice_time},
                    priority=4
                )
        
        # UI deduplication
        elif event_type == "text_input" and source == "ui":
            text = event_data.get("text", "") if event_data else ""
            if text == self._last_ui_text and current_time - self._last_ui_time < self._ui_dedup_window:
                self._decision_counts[DecisionReason.DEDUP_UI_DUPLICATE.value] += 1
                return DecisionResult(
                    accepted=False,
                    reason=DecisionReason.DEDUP_UI_DUPLICATE,
                    details={"source": source, "text": text[:50]},
                    priority=4
                )
        
        return DecisionResult(accepted=True, reason=DecisionReason.ACCEPT, details={}, priority=4)
    
    def _check_system_state(self, priority: int, source: str) -> DecisionResult:
        """Check event against system state."""
        if self._system_state is None:
            return DecisionResult(accepted=True, reason=DecisionReason.ACCEPT, details={}, priority=priority)
        
        # Emergency always accepted
        if priority == 0:  # EMERGENCY
            self._decision_counts[DecisionReason.EMERGENCY_ACCEPT.value] += 1
            return DecisionResult(
                accepted=True,
                reason=DecisionReason.EMERGENCY_ACCEPT,
                details={"priority": priority, "state": self._system_state.name},
                priority=priority
            )
        
        # Drop background tasks in THROTTLED, SAFE, MINIMAL
        if priority == 4 and self._system_state.value >= 1:  # BACKGROUND
            self._decision_counts[DecisionReason.STATE_DROP_BACKGROUND.value] += 1
            return DecisionResult(
                accepted=False,
                reason=DecisionReason.STATE_DROP_BACKGROUND,
                details={"priority": priority, "state": self._system_state.name},
                priority=priority
            )
        
        # Drop screen capture in SAFE, MINIMAL
        if priority == 3 and self._system_state.value >= 2:  # SCREEN_CAPTURE
            self._decision_counts[DecisionReason.STATE_DROP_SCREEN.value] += 1
            return DecisionResult(
                accepted=False,
                reason=DecisionReason.STATE_DROP_SCREEN,
                details={"priority": priority, "state": self._system_state.name},
                priority=priority
            )
        
        # Drop voice in MINIMAL
        if priority == 2 and self._system_state.value >= 3:  # VOICE_INPUT
            self._decision_counts[DecisionReason.STATE_DROP_VOICE.value] += 1
            return DecisionResult(
                accepted=False,
                reason=DecisionReason.STATE_DROP_VOICE,
                details={"priority": priority, "state": self._system_state.name},
                priority=priority
            )
        
        return DecisionResult(accepted=True, reason=DecisionReason.ACCEPT, details={}, priority=priority)
    
    def _check_throttle_factor(self, event_type: str, source: str) -> DecisionResult:
        """Check throttle factor for source-level adaptation."""
        throttle_factor = self._backpressure_layer.get_throttle_factor()
        
        # Critical throttle - reject all
        if throttle_factor < 0.3:
            self._decision_counts[DecisionReason.THROTTLE_CRITICAL.value] += 1
            return DecisionResult(
                accepted=False,
                reason=DecisionReason.THROTTLE_CRITICAL,
                details={"source": source, "throttle_factor": throttle_factor},
                priority=4
            )
        
        # High throttle - reject non-emergency
        if throttle_factor < 0.5:
            self._decision_counts[DecisionReason.THROTTLE_HIGH.value] += 1
            return DecisionResult(
                accepted=False,
                reason=DecisionReason.THROTTLE_HIGH,
                details={"source": source, "throttle_factor": throttle_factor},
                priority=4
            )
        
        return DecisionResult(accepted=True, reason=DecisionReason.ACCEPT, details={}, priority=4)
    
    def update_dedup_state(self, event_type: str, event_data: Optional[dict]) -> None:
        """
        Update deduplication state after successful event submission.
        
        Args:
            event_type: Event type string
            event_data: Optional event data
        """
        current_time = time.time()
        
        if event_type == "voice_input":
            self._last_voice_time = current_time
        elif event_type == "text_input":
            text = event_data.get("text", "") if event_data else ""
            self._last_ui_text = text
            self._last_ui_time = current_time
    
    def get_decision_counts(self) -> Dict[str, int]:
        """Get decision counts for observability."""
        return self._decision_counts.copy()
    
    def reset_decision_counts(self) -> None:
        """Reset decision counts."""
        self._decision_counts = {reason.value: 0 for reason in DecisionReason}
