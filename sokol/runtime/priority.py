"""Event priority policy for event pipeline V2."""

from enum import Enum
from typing import Tuple, Any, Optional


class EventPriority(Enum):
    """Event priority levels - policy, not queue structure."""
    
    EMERGENCY = 0       # Emergency stop, critical safety
    USER_INPUT = 1      # Direct user commands
    VOICE_INPUT = 2     # Voice transcription
    SCREEN_CAPTURE = 3  # Background screen analysis
    BACKGROUND = 4      # Periodic tasks


class PriorityPolicy:
    """
    Event prioritization policy.
    
    Does NOT change queue structure (keeps FIFO).
    Provides:
    - Priority assignment rules
    - Admission control under pressure
    - Priority-aware drop policy
    """
    
    def assign_priority(self, event_type: str, data: Optional[dict] = None) -> int:
        """
        Assign priority to event based on type and context.
        
        Args:
            event_type: Event type string (e.g., "stop", "text_input", "voice_input")
            data: Optional event data dictionary
        
        Returns:
            Priority level (0=highest, higher number=lower priority)
        """
        if event_type == "stop":
            return EventPriority.EMERGENCY.value
        
        elif event_type == "text_input":
            # Check if it's a confirmation/cancel command (higher priority)
            if data and "text" in data:
                text = data["text"].lower().strip()
                # FIX: Added missing emergency keywords to match verification check in _process_event
                # Keywords: ["stop", "стоп", "cancel", "отмена", "emergency", "авария", "abort", "прервать"]
                emergency_keywords = ["да", "нет", "отмена", "стоп", "подтверждаю", "выполняй", 
                                    "yes", "no", "cancel", "stop", "confirm", "execute",
                                    "emergency", "авария", "abort", "прервать"]
                # Check if text contains any emergency keyword (not just exact match)
                if any(keyword in text for keyword in emergency_keywords):
                    return EventPriority.EMERGENCY.value
            return EventPriority.USER_INPUT.value
        
        elif event_type == "voice_input":
            return EventPriority.VOICE_INPUT.value
        
        elif event_type == "screen_capture":
            return EventPriority.SCREEN_CAPTURE.value
        
        elif event_type == "wake_word":
            return EventPriority.VOICE_INPUT.value
        
        return EventPriority.BACKGROUND.value
    
    def should_drop_for_state(
        self, 
        priority: int, 
        system_state
    ) -> Tuple[bool, str]:
        """
        Determine if event should be dropped based on priority and system state (Phase 2.1.2).
        
        Args:
            priority: Event priority level
            system_state: Current system recovery state (SystemState enum)
        
        Returns:
            (drop, reason) tuple
        """
        # Never drop emergency
        if priority == EventPriority.EMERGENCY.value:
            return False, "emergency_protected"
        
        # Drop background tasks in THROTTLED, SAFE, MINIMAL
        if priority == EventPriority.BACKGROUND.value and system_state.value >= 1:
            return True, "background_task_dropped"
        
        # Drop screen capture in SAFE, MINIMAL
        if priority == EventPriority.SCREEN_CAPTURE.value and system_state.value >= 2:
            return True, "screen_capture_dropped"
        
        # Drop voice in MINIMAL
        if priority == EventPriority.VOICE_INPUT.value and system_state.value >= 3:
            return True, "voice_dropped_minimal"
        
        return False, "accept"
