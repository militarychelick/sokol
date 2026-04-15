"""Google AI API LLM client."""

import time
from typing import Any, AsyncIterator, Iterator

from sokol.observability.logging import get_logger

from .base import LLMMessage, LLMProvider, LLMResponse

logger = get_logger("sokol.integrations.llm.google")


class GoogleAIProvider(LLMProvider):
    """Google AI API provider (Gemini)."""

    @property
    def name(self) -> str:
        return "google"

    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Google AI API."""
        try:
            from google import genai
        except ImportError:
            raise RuntimeError("google-genai package not installed")

        # Configure Google AI API
        client = genai.Client(api_key=self.api_key)

        # Convert messages to Google AI format
        # For single completion, use models.generate_content
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        start_time = time.time()

        config_cls = self._resolve_config_class()
        config = config_cls(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
        )

        # Use models.generate_content for text completion
        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.text,
            model=self.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            },
            finish_reason="stop",
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
            from google import genai
        except ImportError:
            raise RuntimeError("google-genai package not installed")

        # Configure Google AI API
        client = genai.Client(api_key=self.api_key)

        # Convert messages to Google AI format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        start_time = time.time()

        config_cls = self._resolve_config_class()
        config = config_cls(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
        )

        # Use models.generate_content for text completion
        response = await client.models.generate_content_async(
            model=self.model,
            contents=contents,
            config=config,
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.text,
            model=self.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            },
            finish_reason="stop",
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
            from google import genai
        except ImportError:
            raise RuntimeError("google-genai package not installed")

        client = genai.Client(api_key=self.api_key)

        # Convert messages to Google AI format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        config_cls = self._resolve_config_class()
        config = config_cls(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
            stream=True
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def stream_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion asynchronously."""
        try:
            from google import genai
        except ImportError:
            raise RuntimeError("google-genai package not installed")

        client = genai.Client(api_key=self.api_key)

        # Convert messages to Google AI format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

        config_cls = self._resolve_config_class()
        config = config_cls(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
        )

        response = await client.models.generate_content_async(
            model=self.model,
            contents=contents,
            config=config,
            stream=True
        )

        async for chunk in response:
            if chunk.text:
                yield chunk.text

    def _resolve_config_class(self):
        """Resolve GenerateContentConfig class across SDK versions."""
        from google import genai
        config_cls = getattr(genai, "GenerateContentConfig", None)
        if config_cls is not None:
            return config_cls
        types_mod = getattr(genai, "types", None)
        if types_mod is not None:
            config_cls = getattr(types_mod, "GenerateContentConfig", None)
            if config_cls is not None:
                return config_cls
        raise RuntimeError("google-genai GenerateContentConfig is unavailable in installed SDK")
