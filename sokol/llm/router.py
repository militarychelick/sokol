"""
LLM router - Hybrid Ollama/OpenAI for Sokol v2
"""

from __future__ import annotations

from typing import Any


class LLMRouter:
    """LLM router (Ollama default, OpenAI for complex tasks)."""
    
    def __init__(self, config: Any) -> None:
        self.config = config
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize LLM clients."""
        try:
            # TODO: Initialize Ollama client
            self._initialized = True
        except Exception:
            self._initialized = False
    
    async def shutdown(self) -> None:
        """Cleanup LLM clients."""
        pass
    
    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        """Generate response from LLM."""
        if not self._initialized:
            raise Exception("LLM not initialized")
        # TODO: Implement LLM generation
