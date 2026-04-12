"""Perception layer - minimal input adapters for future expansion."""

from sokol.perception.text_input import TextInputAdapter, normalize_input
from sokol.perception.voice_input import VoiceInputAdapter, VoiceEvent
from sokol.perception.screen_input import ScreenInputAdapter, ScreenElement, ScreenSnapshot

__all__ = [
    "TextInputAdapter",
    "normalize_input",
    "VoiceInputAdapter",
    "VoiceEvent",
    "ScreenInputAdapter",
    "ScreenElement",
    "ScreenSnapshot",
]
