from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[1]


def resolve_data_dir() -> Path:
    env = os.getenv("NOVA_DATA_DIR") or os.getenv("JARVIS_DATA_DIR")
    if env:
        return Path(env)
    legacy = ROOT / "data"
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "NOVA"
        if (legacy / "settings.json").exists() or (legacy / "nova.db").exists():
            return legacy
        return local
    return legacy


DATA_DIR = resolve_data_dir()
SETTINGS_PATH = DATA_DIR / "settings.json"


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = "auto"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    user_name: str = "Данила"
    assistant_name: str = "Nova"
    language: str = "ru"
    tts_voice: str = "ru-RU-DmitryNeural"
    tts_rate: str = "+12%"
    search_region: str = "ru-ru"
    host: str = "127.0.0.1"
    port: int = 8080
    open_browser: bool = True
    max_history: int = 24
    setup_done: bool = False
    wake_word: bool = True
    theme: str = "dark"
    tts_enabled: bool = True


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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = settings.model_dump()
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
        "setup_done": settings.setup_done,
        "wake_word": settings.wake_word,
        "theme": settings.theme,
        "tts_enabled": settings.tts_enabled,
    }


def infer_provider(settings: Settings) -> str:
    if settings.provider and settings.provider != "auto":
        if settings.provider == "compatible":
            return "openai"
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
    allowed = set(Settings.model_fields)
    for key, value in patch.items():
        if key in allowed and value is not None:
            data[key] = value
    return Settings.model_validate(data)


def clear_api_key(settings: Settings) -> Settings:
    data = settings.model_dump()
    data["api_key"] = ""
    updated = Settings.model_validate(data)
    save_settings(updated)
    return updated
