from __future__ import annotations

import json
from typing import Any

from jarvis.config import DATA_DIR, load_settings

MEMORY_PATH = DATA_DIR / "memory.json"


class ConversationMemory:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if not MEMORY_PATH.exists():
            self.messages = []
            return
        try:
            payload = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            self.messages = payload.get("messages", [])
        except json.JSONDecodeError:
            self.messages = []

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps({"messages": self.messages[-80:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, role: str, content: str) -> None:
        if not content:
            return
        self.messages.append({"role": role, "content": content})
        settings = load_settings()
        self.messages = self.messages[-settings.max_history * 2 :]
        self.save()

    def history(self) -> list[dict[str, Any]]:
        return [m for m in self.messages if m.get("role") in {"user", "assistant", "system"}]

    def clear(self) -> None:
        self.messages = []
        self.save()
