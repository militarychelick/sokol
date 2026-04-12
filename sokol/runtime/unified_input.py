"""Unified input context for perception fusion."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from sokol.perception.voice_input import VoiceEvent
from sokol.perception.screen_input import ScreenSnapshot
from sokol.runtime.intent_model import IntentModel
from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.unified_input")


@dataclass
class UnifiedInputContext:
    """
    Unified input context fusing voice, screen, and text inputs.

    This is the single input object that feeds the orchestrator loop.
    """
    
    # Primary input sources
    voice_text: Optional[str] = None
    voice_confidence: float = 0.0
    user_text: Optional[str] = None
    screen_snapshot: Optional[ScreenSnapshot] = None
    
    # Metadata
    source: str = "unknown"  # voice, text, screen, mixed
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Extracted intent (filled by IntentExtractor)
    intent: Optional[IntentModel] = None
    
    # Context flags
    has_voice: bool = field(init=False)
    has_text: bool = field(init=False)
    has_screen: bool = field(init=False)
    
    def __post_init__(self):
        """Set context flags based on available inputs."""
        self.has_voice = self.voice_text is not None and len(self.voice_text.strip()) > 0
        self.has_text = self.user_text is not None and len(self.user_text.strip()) > 0
        self.has_screen = self.screen_snapshot is not None
    
    def get_primary_text(self) -> str:
        """Get primary text input (voice or user text)."""
        if self.has_voice:
            return self.voice_text
        if self.has_text:
            return self.user_text
        return ""
    
    def is_empty(self) -> bool:
        """Check if context has any input."""
        return not (self.has_voice or self.has_text or self.has_screen)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "voice_text": self.voice_text,
            "voice_confidence": self.voice_confidence,
            "user_text": self.user_text,
            "has_screen": self.has_screen,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent.intent if self.intent else None,
        }
    
    @classmethod
    def from_voice(cls, voice_event: VoiceEvent) -> "UnifiedInputContext":
        """Create context from voice event."""
        return cls(
            voice_text=voice_event.text,
            voice_confidence=voice_event.confidence,
            source="voice",
        )
    
    @classmethod
    def from_text(cls, text: str) -> "UnifiedInputContext":
        """Create context from user text."""
        return cls(
            user_text=text,
            source="text",
        )
    
    @classmethod
    def from_screen(cls, snapshot: ScreenSnapshot) -> "UnifiedInputContext":
        """Create context from screen snapshot."""
        return cls(
            screen_snapshot=snapshot,
            source="screen",
        )
    
    @classmethod
    def from_mixed(
        cls,
        voice_text: Optional[str] = None,
        user_text: Optional[str] = None,
        screen_snapshot: Optional[ScreenSnapshot] = None,
    ) -> "UnifiedInputContext":
        """Create context from multiple input sources."""
        source = "mixed"
        if voice_text and not user_text:
            source = "voice"
        elif user_text and not voice_text:
            source = "text"
        elif screen_snapshot and not (voice_text or user_text):
            source = "screen"
        
        return cls(
            voice_text=voice_text,
            user_text=user_text,
            screen_snapshot=screen_snapshot,
            source=source,
        )
