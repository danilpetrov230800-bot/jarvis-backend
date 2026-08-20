from __future__ import annotations

import json
from pathlib import Path

from jarvis.config import DATA_DIR

PATH = DATA_DIR / "permissions.json"

DEFAULTS = {
    "READ_FILES": True,
    "WRITE_FILES": True,
    "DELETE_FILES": False,
    "RUN_APPLICATIONS": True,
    "SYSTEM_SETTINGS": True,
    "NETWORK": True,
    "SCREEN_CONTROL": True,
    "MICROPHONE": True,
    "CAMERA": False,
    "RESEARCH": False,
}


def load() -> dict[str, bool]:
    data = dict(DEFAULTS)
    if PATH.exists():
        try:
            loaded = json.loads(PATH.read_text(encoding="utf-8"))
            for key, value in loaded.items():
                if key in data:
                    data[key] = bool(value)
        except json.JSONDecodeError:
            pass
    return data


def save(patch: dict[str, bool]) -> dict[str, bool]:
    current = load()
    for key, value in patch.items():
        if key in DEFAULTS:
            current[key] = bool(value)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def allowed(name: str) -> bool:
    return bool(load().get(name, False))


def deny_message(name: str) -> str:
    return f"Действие запрещено настройками: {name}. Включите разрешение в разделе «Доступ»."
