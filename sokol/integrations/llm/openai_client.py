"""OpenAI LLM client."""

import time
from typing import Any, AsyncIterator, Iterator

from sokol.observability.logging import get_logger

from .base import LLMMessage, LLMProvider, LLMResponse

logger = get_logger("sokol.integrations.llm.openai")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    @property
    def name(self) -> str:
        return "openai"

    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed")

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        start_time = time.time()

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            timeout=self.timeout,
            **kwargs,
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
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
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed")

        client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        start_time = time.time()

        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            timeout=self.timeout,
            **kwargs,
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency_ms,
        )

    def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream completion."""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed")

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
            timeout=self.timeout,
            **kwargs,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def stream_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion asynchronously."""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed")

        client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        stream = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
            timeout=self.timeout,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
