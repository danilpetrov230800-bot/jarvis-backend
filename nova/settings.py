from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from nova.constants import DEFAULT_HOST, DEFAULT_PORT, ECHO_GUARD_MS, MAX_HISTORY, WAKE_WORDS
from nova.paths import settings_path
from nova.secretstore import SecretStore


class Settings(BaseModel):
    language: str = "ru"
    user_name: str = ""
    assistant_name: str = "NOVA"
    first_run_complete: bool = False
    theme: str = "dark"
    ui_scale: str = "100"
    start_minimized: bool = False
    launch_at_startup: bool = False

    ai_provider: str = "local"
    ai_model: str = ""
    ai_base_url: str = ""
    ai_temperature: float = 0.6
    ai_timeout_sec: float = 45

    voice_enabled: bool = True
    tts_enabled: bool = True
    stt_enabled: bool = True
    tts_voice: str = "ru-RU-DmitryNeural"
    tts_rate: str = "+10%"
    tts_volume: float = 1.0
    stt_lang: str = "ru-RU"
    microphone_id: str = ""
    speaker_id: str = ""

    wake_word_enabled: bool = True
    wake_words: list[str] = Field(default_factory=lambda: list(WAKE_WORDS))
    wake_sensitivity: float = 0.65
    echo_guard_ms: int = ECHO_GUARD_MS

    memory_auto_save: bool = False
    memory_confirm_personal: bool = True
    max_history: int = MAX_HISTORY

    offline_mode: bool = False
    research_enabled: bool = False
    research_owner_confirmed: bool = False

    notifications_enabled: bool = True
    auto_backup: bool = True
    auto_update_check: bool = True

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    open_window: bool = True

    extra: dict[str, Any] = Field(default_factory=dict)


class SettingsService:
    def __init__(self, path: Path | None = None, secrets: SecretStore | None = None) -> None:
        self.path = path or settings_path()
        self.secrets = secrets or SecretStore()
        self._current = self.load()

    @property
    def current(self) -> Settings:
        return self._current

    def load(self) -> Settings:
        data: dict[str, Any] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        data.pop("api_key", None)
        self._current = Settings.model_validate(data)
        return self._current

    def save(self, settings: Settings | None = None) -> Settings:
        self._current = settings or self._current
        payload = self._current.model_dump(exclude={"extra"})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._current

    def update(self, patch: dict[str, Any]) -> Settings:
        data = self._current.model_dump()
        allowed = set(Settings.model_fields) - {"extra"}
        if "api_key" in patch:
            key = patch.pop("api_key")
            if key and not str(key).endswith("…"):
                self.secrets.set("NOVA_API_KEY", str(key).strip())
        for name, value in patch.items():
            if name in allowed and value is not None:
                data[name] = value
        return self.save(Settings.model_validate(data))

    def public(self) -> dict[str, Any]:
        settings = self._current
        key = self.api_key()
        preview = ""
        if key:
            preview = (key[:3] + "…" + key[-3:]) if len(key) > 8 else "задана"
        payload = settings.model_dump(exclude={"extra"})
        payload.update(
            {
                "has_api_key": bool(key),
                "api_key_preview": preview,
                "resolved_provider": self.resolved_provider(),
                "resolved_model": self.resolved_model(),
                "resolved_base_url": self.resolved_base_url(),
            }
        )
        return payload

    def api_key(self) -> str:
        return self.secrets.get("NOVA_API_KEY") or self.secrets.get("OPENAI_API_KEY")

    def resolved_provider(self) -> str:
        provider = (self._current.ai_provider or "local").lower()
        if provider in {"auto", ""}:
            if self._current.offline_mode:
                return "local"
            if "11434" in self._current.ai_base_url:
                return "ollama"
            if self.api_key():
                return "openai"
            return "local"
        return provider

    def resolved_base_url(self) -> str:
        if self._current.ai_base_url:
            return self._current.ai_base_url.rstrip("/")
        return {
            "openai": "https://api.openai.com/v1",
            "compatible": "https://api.openai.com/v1",
            "ollama": "http://127.0.0.1:11434/v1",
            "local": "",
        }.get(self.resolved_provider(), "")

    def resolved_model(self) -> str:
        if self._current.ai_model:
            return self._current.ai_model
        return {
            "openai": "gpt-4.1-mini",
            "compatible": "gpt-4.1-mini",
            "ollama": "llama3.2",
            "local": "nova-local",
        }.get(self.resolved_provider(), "nova-local")
