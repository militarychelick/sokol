"""LLM manager - coordinates providers with fallback."""

import asyncio
from typing import Any

from sokol.core.config import Config, get_config
from sokol.observability.logging import get_logger

from .base import LLMMessage, LLMProvider, LLMResponse
from .openai_client import OpenAIProvider
from .anthropic_client import AnthropicProvider
from .ollama_client import OllamaProvider
from .google_client import GoogleAIProvider

logger = get_logger("sokol.integrations.llm.manager")


class LLMManager:
    """
    LLM manager with hybrid mode.

    Coordinates multiple providers with automatic fallback.
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or get_config()
        self._providers: dict[str, LLMProvider] = {}
        self._primary_provider: str = self._config.llm.provider
        self._fallback_provider: str = self._config.llm.fallback_provider
        self._fallback_timeout = self._config.llm.fallback_timeout

        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize providers from config."""
        # Google AI
        if self._config.llm.google:
            self._providers["google"] = GoogleAIProvider(
                model=self._config.llm.google.model,
                api_key=self._config.llm.google.api_key,
                base_url=self._config.llm.google.base_url,
                max_tokens=self._config.llm.google.max_tokens,
                temperature=self._config.llm.google.temperature,
            )

        # OpenAI
        if self._config.llm.openai:
            api_key = self._config.get_api_key("openai")
            self._providers["openai"] = OpenAIProvider(
                model=self._config.llm.openai.model,
                api_key=api_key,
                max_tokens=self._config.llm.openai.max_tokens,
                temperature=self._config.llm.openai.temperature,
            )

        # Anthropic
        if self._config.llm.anthropic:
            api_key = self._config.get_api_key("anthropic")
            self._providers["anthropic"] = AnthropicProvider(
                model=self._config.llm.anthropic.model,
                api_key=api_key,
                max_tokens=self._config.llm.anthropic.max_tokens,
                temperature=self._config.llm.anthropic.temperature,
            )

        # Ollama
        if self._config.llm.ollama:
            self._providers["ollama"] = OllamaProvider(
                model=self._config.llm.ollama.model,
                base_url=self._config.llm.ollama.base_url,
                timeout=self._config.llm.ollama.timeout,
                max_tokens=self._config.llm.ollama.max_tokens,
                temperature=self._config.llm.ollama.temperature,
            )

        logger.info_data(
            "LLM providers initialized",
            {
                "providers": list(self._providers.keys()),
                "primary": self._primary_provider,
                "fallback": self._fallback_provider,
            },
        )

    def get_provider(self, name: str | None = None) -> LLMProvider | None:
        """Get provider by name."""
        name = name or self._primary_provider
        return self._providers.get(name)

    def get_primary_provider(self) -> LLMProvider | None:
        """Get primary provider."""
        return self._providers.get(self._primary_provider)

    def get_fallback_provider(self) -> LLMProvider | None:
        """Get fallback provider."""
        return self._providers.get(self._fallback_provider)

    def complete(
        self,
        messages: list[LLMMessage],
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """Get completion from primary or fallback provider."""
        provider_name = self._config.llm.provider
        provider = self._providers.get(provider_name)

        if not provider:
            logger.error(f"Primary provider {provider_name} not found")
            if use_fallback:
                return self._complete_fallback(messages, **kwargs)
            raise ValueError(f"Provider {provider_name} not found")

        try:
            # Log request (minimal)
            logger.info_data("LLM Request", {"provider": provider_name, "msg_count": len(messages)})
            
            response = provider.complete(messages, **kwargs)
            
            # Log response (minimal)
            logger.info_data("LLM Response", {"provider": provider_name, "char_count": len(response.text)})
            
            return response
        except Exception as e:
            import traceback
            logger.error_data(f"Primary provider {provider_name} failed", 
                             {"error": str(e), "traceback": traceback.format_exc()})
            
            if use_fallback:
                return self._complete_fallback(messages, **kwargs)
            
            # If no fallback requested, return empty response instead of crashing
            return LLMResponse(text="LLM error", success=False, provider=provider_name)

    def _complete_fallback(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Try all available providers as fallback."""
        for name, provider in self._providers.items():
            if name == self._config.llm.provider:
                continue
            
            try:
                logger.info(f"Trying fallback provider: {name}")
                return provider.complete(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Fallback provider {name} failed: {e}")
        
        return LLMResponse(text="All LLM providers failed", success=False, provider="none")

    async def complete_async(
        self,
        messages: list[LLMMessage],
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async completion with fallback."""
        provider = self.get_primary_provider()

        if not provider:
            if use_fallback:
                provider = self.get_fallback_provider()
            if not provider:
                raise RuntimeError("No LLM providers available")

        try:
            return await asyncio.wait_for(
                provider.complete_async(messages, **kwargs),
                timeout=self._fallback_timeout,
            )

        except asyncio.TimeoutError:
            logger.warning_data(
                "Primary provider timeout",
                {"provider": provider.name, "timeout": self._fallback_timeout},
            )

            if not use_fallback:
                raise

            fallback = self.get_fallback_provider()
            if fallback and fallback.name != provider.name:
                return await fallback.complete_async(messages, **kwargs)

            raise

        except Exception as e:
            if not use_fallback:
                raise

            fallback = self.get_fallback_provider()
            if fallback and fallback.name != provider.name:
                return await fallback.complete_async(messages, **kwargs)

            raise RuntimeError(f"All providers failed: {e}")

    def is_available(self) -> bool:
        """Check if any provider is available."""
        for provider in self._providers.values():
            if provider.is_available():
                return True
        return False

    def list_providers(self) -> list[str]:
        """List available providers."""
        return list(self._providers.keys())

    def set_primary(self, provider_name: str) -> bool:
        """Set primary provider."""
        if provider_name in self._providers:
            self._primary_provider = provider_name
            logger.info_data("Primary provider changed", {"provider": provider_name})
            return True
        return False


# Global manager instance
_manager: LLMManager | None = None


def get_llm_provider() -> LLMManager:
    """Get global LLM manager."""
    global _manager
    if _manager is None:
        _manager = LLMManager()
    return _manager
