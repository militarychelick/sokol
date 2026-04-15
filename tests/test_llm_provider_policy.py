from sokol.core.config import Config
from sokol.integrations.llm.base import LLMMessage, LLMResponse
from sokol.integrations.llm.manager import LLMManager


class _StubProvider:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        return LLMResponse(
            content=f"{self.name}-ok",
            model="stub",
            provider=self.name,
        )

    async def complete_async(self, messages, **kwargs):
        self.calls += 1
        return LLMResponse(
            content=f"{self.name}-ok",
            model="stub",
            provider=self.name,
        )


def _make_manager() -> LLMManager:
    config = Config()
    config.llm.google.api_key = "key"
    config.llm.provider = "google"
    config.llm.fallback_provider = "ollama"
    manager = LLMManager(config)
    manager._providers = {
        "google": _StubProvider("google"),
        "ollama": _StubProvider("ollama"),
        "openai": _StubProvider("openai"),
        "anthropic": _StubProvider("anthropic"),
    }
    return manager


def test_online_prefers_google():
    manager = _make_manager()
    manager._has_internet_connection = lambda: True
    response = manager.complete([LLMMessage(role="user", content="hi")])
    assert response.provider == "google"


def test_offline_prefers_ollama():
    manager = _make_manager()
    manager._has_internet_connection = lambda: False
    response = manager.complete([LLMMessage(role="user", content="hi")])
    assert response.provider == "ollama"


def test_google_failure_falls_back_only_to_ollama():
    manager = _make_manager()
    manager._has_internet_connection = lambda: True

    def _fail_google(messages, **kwargs):
        raise RuntimeError("google down")

    manager._providers["google"].complete = _fail_google
    response = manager.complete([LLMMessage(role="user", content="hi")], use_fallback=True)
    assert response.provider == "ollama"
