from __future__ import annotations

from typing import Any

from nova.ai.base import AIProvider, ChatMessage, ProviderResult


class LocalProvider(AIProvider):
    name = "local"

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        timeout: float = 45,
    ) -> ProviderResult:
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        text = (
            "Я работаю в локальном режиме без внешней модели. "
            "Команды, файлы, память, навыки и система доступны. "
            f"Последний запрос: «{last[:180]}»."
        )
        return ProviderResult(text=text, provider=self.name, model="nova-local")

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "ok": True, "model": "nova-local"}
