"""
OpenAI client for cloud LLM inference
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from ..core.config import CloudLLMConfig
from ..core.constants import LLMProvider
from ..core.exceptions import LLMError
from .response import LLMResponse


class OpenAIClient:
    """
    Client for OpenAI cloud LLM inference.
    
    Used for complex tasks that need more capable models.
    """
    
    def __init__(self, config: CloudLLMConfig) -> None:
        self.config = config
        self._client: AsyncOpenAI | None = None
    
    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            raise LLMError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                provider="openai",
                model=self.config.model,
            )
        
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=self.config.timeout,
        )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            **kwargs: Additional parameters
        
        Returns:
            LLMResponse with generated text
        """
        if self._client is None:
            await self.initialize()
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", 0.7),
            )
            
            choice = response.choices[0]
            
            return LLMResponse(
                text=choice.message.content or "",
                provider=LLMProvider.OPENAI,
                model=self.config.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                finish_reason=choice.finish_reason or "stop",
            )
            
        except Exception as e:
            raise LLMError(
                "OpenAI generation failed",
                provider="openai",
                model=self.config.model,
            ) from e
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ):
        """
        Generate text completion with streaming.
        
        Yields text chunks as they're generated.
        """
        if self._client is None:
            await self.initialize()
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", 0.7),
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise LLMError(
                "OpenAI streaming failed",
                provider="openai",
                model=self.config.model,
            ) from e
    
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        if self._client is None:
            await self.initialize()
        
        try:
            response = await self._client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            raise LLMError(
                "OpenAI embedding failed",
                provider="openai",
                model="text-embedding-3-small",
            ) from e
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._client:
            await self._client.close()
            self._client = None
