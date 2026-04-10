"""
LLM router - Routes between local (Ollama) and online (ChatGPT)
"""

from __future__ import annotations

from typing import Any

from .llm import LLMClient
from ..core.config import Config


class LLMRouter:
    """Router for LLM selection based on context and availability."""
    
    def __init__(self, config: Config, llm_client: LLMClient) -> None:
        self.config = config
        self.llm_client = llm_client
    
    async def route(
        self,
        prompt: str,
        system_prompt: str | None = None,
        force_online: bool = False,
        force_local: bool = False,
        **kwargs: Any,
    ) -> str:
        """Route request to appropriate LLM."""
        if force_local:
            return await self.llm_client.generate_local(prompt, system_prompt, **kwargs)
        
        if force_online:
            return await self.llm_client.generate_online(prompt, system_prompt, **kwargs)
        
        # Use routing logic from config
        if self.config.llm.routing.prefer_local:
            try:
                return await self.llm_client.generate_local(prompt, system_prompt, **kwargs)
            except Exception:
                if self.config.llm.cloud.api_key:
                    return await self.llm_client.generate_online(prompt, system_prompt, **kwargs)
                raise
        else:
            if self.config.llm.cloud.api_key:
                return await self.llm_client.generate_online(prompt, system_prompt, **kwargs)
            return await self.llm_client.generate_local(prompt, system_prompt, **kwargs)
    
    async def route_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Route JSON request."""
        response = await self.route(prompt, system_prompt, **kwargs)
        import json
        return json.loads(response)
