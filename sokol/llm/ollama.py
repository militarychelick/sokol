"""
Ollama client for local LLM inference
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import ollama

from ..core.config import LocalLLMConfig
from ..core.constants import LLMProvider
from ..core.exceptions import LLMError
from .response import LLMResponse


class OllamaClient:
    """
    Client for Ollama local LLM inference.
    
    Ollama runs locally and provides OpenAI-compatible API.
    """
    
    def __init__(self, config: LocalLLMConfig) -> None:
        self.config = config
        self._client: ollama.Client | None = None
        self._http_client: httpx.AsyncClient | None = None
    
    async def initialize(self) -> None:
        """Initialize Ollama client."""
        try:
            self._client = ollama.Client(host=self.config.base_url)
            self._http_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            
            # Verify connection
            await self._check_connection()
            
        except Exception as e:
            raise LLMError(
                "Failed to connect to Ollama",
                provider="ollama",
                model=self.config.model,
            ) from e
    
    async def _check_connection(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            models = self._client.list()
            model_names = [m["name"] for m in models.get("models", [])]
            
            # Check if our model is available
            if self.config.model not in model_names:
                # Try to pull the model
                self._client.pull(self.config.model)
            
            return True
            
        except Exception as e:
            raise LLMError(
                f"Ollama not running or model '{self.config.model}' unavailable",
                provider="ollama",
                model=self.config.model,
            ) from e
    
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
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.chat(
                    model=self.config.model,
                    messages=messages,
                    options={
                        "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
                        "temperature": kwargs.get("temperature", 0.7),
                    },
                ),
            )
            
            return LLMResponse(
                text=response["message"]["content"],
                provider=LLMProvider.OLLAMA,
                model=self.config.model,
                tokens_used=response.get("eval_count", 0) + response.get("prompt_eval_count", 0),
                finish_reason="stop",
            )
            
        except Exception as e:
            raise LLMError(
                "Ollama generation failed",
                provider="ollama",
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
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            for chunk in self._client.chat(
                model=self.config.model,
                messages=messages,
                stream=True,
                options={
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            ):
                if "message" in chunk:
                    yield chunk["message"]["content"]
                    
        except Exception as e:
            raise LLMError(
                "Ollama streaming failed",
                provider="ollama",
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
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.embeddings(
                    model=self.config.model,
                    prompt=text,
                ),
            )
            
            return response["embedding"]
            
        except Exception as e:
            raise LLMError(
                "Ollama embedding failed",
                provider="ollama",
                model=self.config.model,
            ) from e
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        self._client = None
