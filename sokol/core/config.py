"""Configuration loader and manager."""

import os
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import BaseModel, Field

from sokol.core.constants import DEFAULT_CONFIG_PATH


class LLMProviderConfig(BaseModel):
    """LLM provider configuration."""

    model: str = "gpt-4o"
    api_key_env: str | None = None
    api_key: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    base_url: str | None = None
    timeout: float = 30.0


class VoiceConfig(BaseModel):
    """Voice configuration."""

    enabled: bool = False
    wake_word_engine: str = "porcupine"
    stt_engine: str = "whisper"
    tts_engine: str = "edge-tts"


class PerceptionConfig(BaseModel):
    """Perception input configuration."""

    enable_voice_input: bool = False
    enable_screen_input: bool = False


class SafetyConfig(BaseModel):
    """Safety configuration."""

    confirm_dangerous: bool = True
    dangerous_tools: list[str] = Field(
        default_factory=lambda: [
            "file_delete",
            "file_write",
            "app_close",
            "system_shutdown",
        ]
    )
    max_retries: int = 3


class MemoryConfig(BaseModel):
    """Memory configuration."""

    session_ttl: int = 3600
    profile_path: str = "data/profile.db"
    longterm_path: str = "data/longterm.db"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "logs/sokol.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "json"


class UIConfig(BaseModel):
    """UI configuration."""

    theme: str = "dark"
    start_minimized: bool = False
    show_on_startup: bool = True
    tray_icon: bool = True


class AutomationConfig(BaseModel):
    """Automation configuration."""

    uia_timeout: float = 5.0
    browser_timeout: float = 10.0
    ocr_fallback: bool = True


class AgentConfig(BaseModel):
    """Agent configuration."""

    name: str = "Sokol"
    wake_words: list[str] = Field(
        default_factory=lambda: ["sokol", "cokol", "sockol"]
    )
    language: str = "ru"
    response_style: str = "brief"


class LLMConfig(BaseModel):
    """LLM top-level configuration."""

    provider: str = "openai"
    fallback_provider: str = "ollama"
    fallback_timeout: float = 10.0
    openai: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    anthropic: LLMProviderConfig = Field(
        default_factory=lambda: LLMProviderConfig(
            model="claude-3-sonnet-20240229",
            api_key_env="ANTHROPIC_API_KEY",
        )
    )
    ollama: LLMProviderConfig = Field(
        default_factory=lambda: LLMProviderConfig(
            model="llama3",
            base_url="http://localhost:11434",
        )
    )


class Config(BaseModel):
    """Root configuration model."""

    agent: AgentConfig = Field(default_factory=AgentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)

    @classmethod
    def from_file(cls, path: Path | None = None) -> "Config":
        """Load configuration from TOML file."""
        path = path or DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomli.load(f)

        return cls.model_validate(data)

    def to_file(self, path: Path | None = None) -> None:
        """Save configuration to TOML file."""
        path = path or DEFAULT_CONFIG_PATH
        data = self.model_dump(mode="json", exclude_none=True)

        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    def get_api_key(self, provider: str) -> str | None:
        """Get API key for provider from config or environment."""
        # First check config file
        if provider == "openai" and self.llm.openai.api_key:
            return self.llm.openai.api_key
        if provider == "anthropic" and self.llm.anthropic.api_key:
            return self.llm.anthropic.api_key

        # Fallback to environment variable
        provider_configs = {
            "openai": self.llm.openai.api_key_env,
            "anthropic": self.llm.anthropic.api_key_env,
        }
        env_var = provider_configs.get(provider)
        if env_var:
            return os.environ.get(env_var)
        return None


def load_config(path: Path | None = None) -> Config:
    """Load configuration, with defaults for missing values."""
    return Config.from_file(path)


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(path: Path | None = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = load_config(path)
    return _config
