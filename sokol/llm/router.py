"""
LLM Router - decides between local and cloud LLM
"""

from __future__ import annotations

from typing import Any

from ..core.config import LLMConfig
from ..core.constants import LLMProvider
from ..core.exceptions import LLMError
from .ollama import OllamaClient
from .openai import OpenAIClient
from .response import LLMResponse


class LLMRouter:
    """
    Routes LLM requests to appropriate provider.
    
    Decision factors:
    - Task complexity
    - Privacy requirements
    - User preference
    - Local model capability
    """
    
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._local: OllamaClient | None = None
        self._cloud: OpenAIClient | None = None
    
    async def initialize(self) -> None:
        """Initialize LLM clients."""
        # Initialize local client (primary)
        self._local = OllamaClient(self.config.local)
        try:
            await self._local.initialize()
        except LLMError:
            # Local not available, will rely on cloud
            self._local = None
        
        # Initialize cloud client (fallback)
        self._cloud = OpenAIClient(self.config.cloud)
        try:
            await self._cloud.initialize()
        except LLMError:
            # Cloud not configured
            self._cloud = None
        
        # Verify at least one is available
        if not self._local and not self._cloud:
            raise LLMError(
                "No LLM available. Configure Ollama (local) or set OPENAI_API_KEY (cloud)."
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        complexity: int = 1,
        requires_privacy: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate text completion using appropriate provider.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            complexity: Task complexity (1-10)
            requires_privacy: If True, prefer local
            **kwargs: Additional parameters
        
        Returns:
            LLMResponse from selected provider
        """
        provider = self._select_provider(complexity, requires_privacy)
        
        if provider == LLMProvider.OLLAMA and self._local:
            return await self._local.generate(prompt, system_prompt, **kwargs)
        elif provider == LLMProvider.OPENAI and self._cloud:
            return await self._cloud.generate(prompt, system_prompt, **kwargs)
        else:
            # Fallback to available provider
            if self._local:
                return await self._local.generate(prompt, system_prompt, **kwargs)
            elif self._cloud:
                return await self._cloud.generate(prompt, system_prompt, **kwargs)
            else:
                raise LLMError("No LLM provider available")
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        complexity: int = 1,
        requires_privacy: bool = False,
        **kwargs: Any,
    ):
        """
        Generate text completion with streaming.
        
        Yields text chunks as they're generated.
        """
        provider = self._select_provider(complexity, requires_privacy)
        
        if provider == LLMProvider.OLLAMA and self._local:
            async for chunk in self._local.generate_stream(prompt, system_prompt, **kwargs):
                yield chunk
        elif provider == LLMProvider.OPENAI and self._cloud:
            async for chunk in self._cloud.generate_stream(prompt, system_prompt, **kwargs):
                yield chunk
        else:
            # Fallback
            if self._local:
                async for chunk in self._local.generate_stream(prompt, system_prompt, **kwargs):
                    yield chunk
            elif self._cloud:
                async for chunk in self._cloud.generate_stream(prompt, system_prompt, **kwargs):
                    yield chunk
            else:
                raise LLMError("No LLM provider available")
    
    async def embed(self, text: str, prefer_local: bool = True) -> list[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            prefer_local: Prefer local embedding if available
        
        Returns:
            Embedding vector
        """
        if prefer_local and self._local:
            try:
                return await self._local.embed(text)
            except LLMError:
                pass  # Fall back to cloud
        
        if self._cloud:
            return await self._cloud.embed(text)
        
        raise LLMError("No embedding provider available")
    
    def _select_provider(
        self,
        complexity: int,
        requires_privacy: bool,
    ) -> LLMProvider:
        """
        Select appropriate LLM provider.
        
        Decision logic:
        1. If privacy required -> local
        2. If complexity > threshold and cloud available -> cloud
        3. Otherwise -> local (prefer_local setting)
        """
        # Privacy requirement forces local
        if requires_privacy and self.config.routing.local_for_private and self._local:
            return LLMProvider.OLLAMA
        
        # High complexity prefers cloud
        if (
            complexity >= self.config.routing.complexity_threshold
            and self.config.routing.cloud_for_complex
            and self._cloud
        ):
            return LLMProvider.OPENAI
        
        # Default to local preference
        if self.config.routing.prefer_local and self._local:
            return LLMProvider.OLLAMA
        
        # Cloud fallback
        if self._cloud:
            return LLMProvider.OPENAI
        
        # Last resort: local
        return LLMProvider.OLLAMA
    
    def get_available_providers(self) -> list[LLMProvider]:
        """Get list of available providers."""
        providers = []
        if self._local:
            providers.append(LLMProvider.OLLAMA)
        if self._cloud:
            providers.append(LLMProvider.OPENAI)
        return providers
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._local:
            await self._local.shutdown()
        if self._cloud:
            await self._cloud.shutdown()
