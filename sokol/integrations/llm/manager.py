"""LLM manager - coordinates providers with fallback."""

import asyncio
from typing import Any

from sokol.core.config import Config, get_config
from sokol.observability.logging import get_logger

from .base import LLMMessage, LLMProvider, LLMResponse
from .openai_client import OpenAIProvider
from .anthropic_client import AnthropicProvider
from .ollama_client import OllamaProvider

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
        """
        Generate completion with fallback.

        Tries primary provider first, falls back on failure/timeout.
        """
        provider = self.get_primary_provider()

        if not provider:
            logger.warning("No primary provider available")
            if use_fallback:
                provider = self.get_fallback_provider()
            if not provider:
                raise RuntimeError("No LLM providers available")

        # Try primary
        try:
            logger.debug_data(
                "Trying primary provider",
                {"provider": provider.name, "model": provider.model},
            )
            return provider.complete(messages, **kwargs)

        except Exception as e:
            logger.error_data(
                "Primary provider failed",
                {"provider": provider.name, "error": str(e)},
            )

            if not use_fallback:
                raise

            # Try fallback
            fallback = self.get_fallback_provider()
            if fallback and fallback.name != provider.name:
                logger.info_data(
                    "Using fallback provider",
                    {"provider": fallback.name},
                )
                try:
                    return fallback.complete(messages, **kwargs)
                except Exception as fallback_error:
                    logger.error_data(
                        "Fallback provider also failed",
                        {"provider": fallback.name, "error": str(fallback_error)},
                    )

            raise RuntimeError(f"All providers failed: {e}")

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
