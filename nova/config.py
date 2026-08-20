"""
NOVA System Configuration and Paths
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = Path(os.getenv("NOVA_DATA_DIR", ROOT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "nova.db"
BACKUPS_DIR = DATA_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TTS_CACHE_DIR = DATA_DIR / "tts_cache"
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SecuritySettings(BaseModel):
    allow_file_read: bool = True
    allow_file_write: bool = True
    allow_file_delete: bool = False
    allow_app_launch: bool = True
    allow_system_control: bool = True
    allow_network: bool = True
    allow_screen_capture: bool = True
    allow_microphone: bool = True
    allow_cmd_execution: bool = False
    require_confirmation_for_dangerous: bool = True


class AISettings(BaseModel):
    provider: Literal["local", "openai", "ollama", "compatible"] = "local"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    ollama_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = (
        "Ты NOVA — Neural Operational & Virtual Assistant. "
        "Умный, надежный и безопасный персональный ассистент для Windows. "
        "Отвечай кратко, четко, доброжелательно и по существу."
    )


class VoiceSettings(BaseModel):
    enabled: bool = True
    wake_word_enabled: bool = True
    wake_words: list[str] = Field(default_factory=lambda: ["нова", "nova", "привет нова", "слушай нова"])
    wake_word_sensitivity: float = 0.6
    voice: str = "ru-RU-DmitryNeural"
    speech_rate: str = "+10%"
    volume: float = 1.0
    mic_device: str = "default"
    prevent_echo: bool = True


class AppSettings(BaseModel):
    theme: Literal["dark", "light", "system"] = "dark"
    ui_scale: float = 1.0
    sound_effects: bool = True
    startup_diagnostics: bool = True
    auto_backup: bool = True
    research_mode_unlocked: bool = False
    research_password_hash: str = ""
    ai: AISettings = Field(default_factory=AISettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
