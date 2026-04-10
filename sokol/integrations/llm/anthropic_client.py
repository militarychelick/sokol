"""Anthropic Claude LLM client."""

import time
from typing import Any, AsyncIterator

from sokol.observability.logging import get_logger

from .base import LLMMessage, LLMProvider, LLMResponse

logger = get_logger("sokol.integrations.llm.anthropic")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    @property
    def name(self) -> str:
        return "anthropic"

    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed")

        client = anthropic.Anthropic(api_key=self.api_key)

        # Extract system message
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        start_time = time.time()

        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system_prompt,
            messages=chat_messages,
            timeout=self.timeout,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Extract text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "stop",
            latency_ms=latency_ms,
        )

    async def complete_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion asynchronously."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed")

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Extract system message
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        start_time = time.time()

        response = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system_prompt,
            messages=chat_messages,
            timeout=self.timeout,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Extract text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "stop",
            latency_ms=latency_ms,
        )

    async def stream_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion asynchronously."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed")

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Extract system message
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system_prompt,
            messages=chat_messages,
            timeout=self.timeout,
        ) as stream:
            async for text in stream.text_stream:
                yield text
