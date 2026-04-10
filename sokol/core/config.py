"""
Configuration management for Sokol v2
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    """Voice layer configuration."""
    wake_word: str | None = None
    ptt_key: str = "f12"
    tts_voice: str = "ru-RU-DmitryNeural"
    tts_rate: str = "+0%"
    stt_model: str = "medium"
    stt_language: str | None = None
    vad_sensitivity: int = Field(default=3, ge=1, le=5)
    listen_timeout: float = Field(default=30.0, gt=0)


class LocalLLMConfig(BaseModel):
    """Local LLM configuration."""
    provider: str = "ollama"
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    timeout: float = Field(default=60.0, gt=0)
    max_tokens: int = Field(default=2048, gt=0)


class CloudLLMConfig(BaseModel):
    """Cloud LLM configuration."""
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    timeout: float = Field(default=30.0, gt=0)
    max_tokens: int = Field(default=4096, gt=0)


class LLMRoutingConfig(BaseModel):
    """LLM routing preferences."""
    prefer_local: bool = True
    cloud_for_complex: bool = True
    cloud_for_reasoning: bool = True
    local_for_private: bool = True
    complexity_threshold: int = Field(default=5, ge=1, le=10)


class LLMConfig(BaseModel):
    """Complete LLM configuration."""
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    cloud: CloudLLMConfig = Field(default_factory=CloudLLMConfig)
    routing: LLMRoutingConfig = Field(default_factory=LLMRoutingConfig)


class SafetyConfig(BaseModel):
    """Safety policy configuration."""
    code_execution: bool = False
    require_confirmation: list[str] = Field(
        default_factory=lambda: [
            "file_delete",
            "file_modify",
            "system_settings",
            "unknown_urls",
        ]
    )
    audit_all_actions: bool = True
    max_retries: int = Field(default=3, ge=0)


class MemoryConfig(BaseModel):
    """Memory system configuration."""
    session_limit: int = Field(default=100, ge=10)
    profile_auto_save: bool = True
    habit_min_frequency: int = Field(default=3, ge=1)
    retention_days: int = Field(default=30, ge=1)


class GUIConfig(BaseModel):
    """GUI configuration."""
    show_on_start: bool = True
    minimize_to_tray: bool = True
    start_minimized: bool = False
    theme: str = "dark"
    window_width: int = Field(default=800, ge=400)
    window_height: int = Field(default=600, ge=300)


class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str = "Sokol"
    language: str = "ru"
    response_style: str = "friendly"  # friendly, formal, minimal


class Config(BaseModel):
    """Complete Sokol configuration."""
    agent: AgentConfig = Field(default_factory=AgentConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    gui: GUIConfig = Field(default_factory=GUIConfig)
    
    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from file(s).
        
        Order of precedence:
        1. config_path parameter (if provided)
        2. Environment variables
        3. config/local.yaml (user overrides)
        4. config/default.yaml (defaults)
        """
        # Default config path
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config"
        
        # Start with defaults
        config_data: dict[str, Any] = {}
        
        # Load default.yaml
        default_path = config_path / "default.yaml"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        
        # Load local.yaml (user overrides)
        local_path = config_path / "local.yaml"
        if local_path.exists():
            with open(local_path, "r", encoding="utf-8") as f:
                local_data = yaml.safe_load(f) or {}
                config_data = cls._deep_merge(config_data, local_data)
        
        # Override with environment variables
        config_data = cls._apply_env_overrides(config_data)
        
        return cls(**config_data)
    
    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def _apply_env_overrides(config: dict) -> dict:
        """Apply environment variable overrides."""
        # OpenAI API key
        if api_key := os.environ.get("OPENAI_API_KEY"):
            if "llm" not in config:
                config["llm"] = {}
            if "cloud" not in config["llm"]:
                config["llm"]["cloud"] = {}
            config["llm"]["cloud"]["api_key"] = api_key
        
        # Ollama base URL
        if ollama_url := os.environ.get("OLLAMA_HOST"):
            if "llm" not in config:
                config["llm"] = {}
            if "local" not in config["llm"]:
                config["llm"]["local"] = {}
            config["llm"]["local"]["base_url"] = ollama_url
        
        return config
    
    def save_local(self, config_path: Path | None = None) -> None:
        """Save current configuration to local.yaml."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config"
        
        local_path = config_path / "local.yaml"
        
        with open(local_path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from files."""
    global _config
    _config = Config.load()
    return _config
