"""LLM provider base class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Iterator


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class LLMMessage:
    """Message for LLM conversation."""

    role: str  # system, user, assistant
    content: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion."""
        pass

    @abstractmethod
    async def complete_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion asynchronously."""
        pass

    def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream completion. Override if supported."""
        response = self.complete(messages, max_tokens, temperature, **kwargs)
        yield response.content

    async def stream_async(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion asynchronously. Override if supported."""
        response = await self.complete_async(
            messages, max_tokens, temperature, **kwargs
        )
        yield response.content

    def is_available(self) -> bool:
        """Check if provider is available."""
        return self.api_key is not None or self.base_url is not None

    def build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Build system prompt for the agent."""
        base_prompt = """You are Sokol, a Windows AI assistant.

Your role:
- Help users manage their Windows PC through voice and text commands
- Execute commands safely, always asking for confirmation for dangerous actions
- Provide brief, clear responses (especially for voice output)
- Be proactive but not autonomous - always involve the user

Guidelines:
- Keep responses under 2-3 sentences for voice output
- Ask for confirmation before: deleting files, closing apps, system changes
- If unsure, ask clarifying questions
- Report errors clearly with actionable suggestions
- Use available tools to accomplish tasks

Available capabilities:
- Launch applications
- Manage windows (minimize, maximize, close)
- File operations (read, write, list)
- System information queries
"""
        if context:
            base_prompt += f"\nCurrent context:\n"
            for key, value in context.items():
                base_prompt += f"- {key}: {value}\n"

        return base_prompt

    def __repr__(self) -> str:
        return f"LLMProvider(name={self.name}, model={self.model})"
