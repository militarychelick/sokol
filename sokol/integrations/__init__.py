"""Integrations module - LLM, voice, browser backends."""

from sokol.integrations.llm import LLMProvider, LLMResponse, get_llm_provider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "get_llm_provider",
]
