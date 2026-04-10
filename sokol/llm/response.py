"""
LLM Response models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.constants import LLMProvider


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    text: str
    provider: LLMProvider
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def is_complete(self) -> bool:
        """Check if response is complete."""
        return self.finish_reason == "stop"
    
    def is_truncated(self) -> bool:
        """Check if response was truncated."""
        return self.finish_reason == "length"


@dataclass
class EmbeddingResult:
    """Result of text embedding."""
    vector: list[float]
    provider: LLMProvider
    model: str
    dimensions: int
    
    @property
    def size(self) -> int:
        return len(self.vector)
