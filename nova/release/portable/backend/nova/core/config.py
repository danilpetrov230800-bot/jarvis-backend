"""NOVA configuration and paths."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_data_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    data = base / "NOVA"
    data.mkdir(parents=True, exist_ok=True)
    return data


class NovaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOVA_", extra="ignore")

    app_name: str = "NOVA"
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 47821
    debug: bool = False
    offline_mode: bool = False
    language: str = "ru"
    theme: Literal["dark", "light", "system"] = "dark"

    ai_provider: Literal["openai", "ollama", "local", "compatible"] = "local"
    ai_model: str = "gpt-4o-mini"
    ollama_url: str = "http://127.0.0.1:11434"
    compatible_api_url: str = ""

    voice_enabled: bool = True
    wake_word_enabled: bool = True
    wake_word_sensitivity: float = 0.5
    tts_rate: int = 180
    tts_volume: float = 1.0

    agent_max_steps: int = 20
    agent_timeout_sec: int = 300
    agent_retry_limit: int = 3

    first_run_complete: bool = False
    research_mode_enabled: bool = False

    @property
    def data_dir(self) -> Path:
        return get_data_dir()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nova.db"

    @property
    def logs_dir(self) -> Path:
        path = self.data_dir / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def backups_dir(self) -> Path:
        path = self.data_dir / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path


_settings: NovaSettings | None = None


def get_settings() -> NovaSettings:
    global _settings
    if _settings is None:
        _settings = NovaSettings()
    return _settings


def reload_settings() -> NovaSettings:
    global _settings
    _settings = NovaSettings()
    return _settings
