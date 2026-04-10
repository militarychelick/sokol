"""
LLM client - Ollama (local) + ChatGPT (online)
"""

from __future__ import annotations

import json
from typing import Any

import httpx

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    AsyncOpenAI = None

from ..core.config import Config


class LLMClient:
    """LLM client with local (Ollama) and online (ChatGPT) support."""
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._ollama_client: httpx.AsyncClient | None = None
        self._openai_client: AsyncOpenAI | None = None
    
    async def _get_ollama_client(self) -> httpx.AsyncClient:
        """Get or create Ollama client."""
        if self._ollama_client is None:
            self._ollama_client = httpx.AsyncClient(
                base_url=self.config.llm.local.base_url,
                timeout=self.config.llm.local.timeout,
            )
        return self._ollama_client
    
    async def _get_openai_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if not HAS_OPENAI:
            raise ValueError("OpenAI library not installed")
        if self._openai_client is None:
            api_key = self.config.llm.cloud.api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            self._openai_client = AsyncOpenAI(api_key=api_key)
        return self._openai_client
    
    async def generate_local(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate response using Ollama (local)."""
        client = await self._get_ollama_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await client.post(
            "/api/chat",
            json={
                "model": self.config.llm.local.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": kwargs.get("max_tokens", self.config.llm.local.max_tokens),
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
    
    async def generate_online(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate response using ChatGPT (online)."""
        client = await self._get_openai_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await client.chat.completions.create(
            model=self.config.llm.cloud.model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.llm.cloud.max_tokens),
        )
        return response.choices[0].message.content
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_local: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate JSON response."""
        response = await self.generate(
            prompt,
            system_prompt,
            use_local=use_local,
            **kwargs,
        )
        return json.loads(response)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_local: bool = True,
        **kwargs: Any,
    ) -> str:
        """Generate response (auto-route based on config)."""
        if use_local and self.config.llm.routing.prefer_local:
            try:
                return await self.generate_local(prompt, system_prompt, **kwargs)
            except Exception:
                # Fallback to online if local fails
                if self.config.llm.cloud.api_key:
                    return await self.generate_online(prompt, system_prompt, **kwargs)
                raise
        elif self.config.llm.cloud.api_key:
            return await self.generate_online(prompt, system_prompt, **kwargs)
        else:
            return await self.generate_local(prompt, system_prompt, **kwargs)
    
    async def shutdown(self) -> None:
        """Cleanup clients."""
        if self._ollama_client:
            await self._ollama_client.aclose()
        if self._openai_client:
            await self._openai_client.close()
