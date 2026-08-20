from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _user_data_dir() -> Path:
    override = os.getenv("NOVA_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NOVA"
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "nova"


DATA_DIR = _user_data_dir()
SETTINGS_PATH = DATA_DIR / "settings.json"


class Settings(BaseModel):
    provider: str = "auto"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    user_name: str = "Пользователь"
    assistant_name: str = "Nova"
    language: str = "ru"
    tts_voice: str = "ru-RU-DmitryNeural"
    tts_rate: str = "+12%"
    search_region: str = "ru-ru"
    host: str = "127.0.0.1"
    port: int = 8080
    open_browser: bool = False
    max_history: int = 24

    extra: dict[str, Any] = Field(default_factory=dict)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def load_settings() -> Settings:
    file_data = {k: v for k, v in _read_json(SETTINGS_PATH).items() if v not in ("", None)}
    settings = Settings.model_validate(file_data)
    from jarvis.secrets import load_api_key

    stored_key = load_api_key()
    if stored_key:
        settings.api_key = stored_key

    settings.user_name = os.getenv("NOVA_USER_NAME", os.getenv("JARVIS_USER_NAME", settings.user_name))
    settings.assistant_name = os.getenv("NOVA_ASSISTANT_NAME", os.getenv("JARVIS_ASSISTANT_NAME", settings.assistant_name))
    settings.tts_voice = os.getenv("NOVA_TTS_VOICE", os.getenv("JARVIS_TTS_VOICE", settings.tts_voice))
    settings.host = os.getenv("NOVA_HOST", os.getenv("JARVIS_HOST", settings.host))
    settings.port = int(os.getenv("NOVA_PORT", os.getenv("JARVIS_PORT", settings.port)))
    settings.provider = os.getenv("NOVA_PROVIDER", os.getenv("JARVIS_PROVIDER", settings.provider)).lower()
    settings.model = os.getenv("NOVA_MODEL", os.getenv("JARVIS_MODEL", os.getenv("OPENAI_MODEL", settings.model)))
    settings.base_url = os.getenv("NOVA_BASE_URL", os.getenv("JARVIS_BASE_URL", os.getenv("OPENAI_BASE_URL", settings.base_url)))

    env_key = _first_env(
        "NOVA_API_KEY",
        "JARVIS_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
    )
    if env_key:
        settings.api_key = env_key
    return settings


def save_settings(settings: Settings) -> None:
    from jarvis.secrets import save_api_key

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_api_key(settings.api_key)
    payload = settings.model_dump(exclude={"extra", "api_key"})
    SETTINGS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def public_settings(settings: Settings) -> dict[str, Any]:
    key = settings.api_key
    masked = (key[:4] + "…" + key[-4:]) if len(key) > 8 else ("задана" if key else "")
    return {
        "provider": settings.provider,
        "model": settings.model or inferred_model(settings),
        "base_url": settings.base_url or inferred_base_url(settings),
        "user_name": settings.user_name,
        "assistant_name": settings.assistant_name,
        "language": settings.language,
        "tts_voice": settings.tts_voice,
        "tts_rate": settings.tts_rate,
        "search_region": settings.search_region,
        "has_api_key": bool(settings.api_key),
        "api_key_preview": masked,
        "resolved_provider": infer_provider(settings),
    }


def infer_provider(settings: Settings) -> str:
    if settings.provider and settings.provider != "auto":
        return settings.provider
    if "openrouter" in settings.base_url or os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if "groq" in settings.base_url or os.getenv("GROQ_API_KEY"):
        return "groq"
    if "11434" in settings.base_url or settings.provider == "ollama":
        return "ollama"
    if settings.api_key or os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "openai"


def inferred_base_url(settings: Settings) -> str:
    if settings.base_url:
        return settings.base_url.rstrip("/")
    provider = infer_provider(settings)
    return {
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "ollama": "http://127.0.0.1:11434/v1",
        "openai": "https://api.openai.com/v1",
    }.get(provider, "https://api.openai.com/v1")


def inferred_model(settings: Settings) -> str:
    if settings.model:
        return settings.model
    provider = infer_provider(settings)
    return {
        "openrouter": "x-ai/grok-4-fast",
        "groq": "llama-3.3-70b-versatile",
        "ollama": "qwen2.5:14b",
        "openai": "gpt-4.1-mini",
    }.get(provider, "gpt-4.1-mini")


def merge_settings(current: Settings, patch: dict[str, Any]) -> Settings:
    data = current.model_dump()
    allowed = set(Settings.model_fields) - {"extra"}
    for key, value in patch.items():
        if key in allowed and value is not None:
            data[key] = value
    return Settings.model_validate(data)
