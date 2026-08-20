"""OpenAI-compatible API provider."""

from __future__ import annotations

import httpx

from nova.ai.provider import AIMessage, AIProvider, AIResponse
from nova.core.config import get_settings
from nova.core.logging import get_logger
from nova.security.secrets import get_secret_store

logger = get_logger("nova.ai.compatible")


class CompatibleAPIProvider(AIProvider):
    name = "compatible"

    def __init__(self):
        self.settings = get_settings()

    async def is_available(self) -> bool:
        if not self.settings.compatible_api_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.settings.compatible_api_url.rstrip('/')}/models")
                return r.status_code in (200, 404)
        except Exception:
            return False

    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        url = self.settings.compatible_api_url.rstrip("/")
        api_key = get_secret_store().get("compatible_api_key") or "not-needed"

        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self.settings.ai_model,
                    "messages": api_messages,
                },
            )
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]
        return AIResponse(
            content=content,
            model=self.settings.ai_model,
            provider=self.name,
        )
