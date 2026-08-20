"""Ollama local model provider."""

from __future__ import annotations

import httpx

from nova.ai.provider import AIMessage, AIProvider, AIResponse
from nova.core.config import get_settings
from nova.core.logging import get_logger

logger = get_logger("nova.ai.ollama")


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self):
        self.settings = get_settings()

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.settings.ollama_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        payload = {
            "model": self.settings.ai_model or "llama3.2",
            "messages": api_messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.settings.ollama_url}/api/chat",
                json=payload,
            )
            r.raise_for_status()
            data = r.json()

        return AIResponse(
            content=data.get("message", {}).get("content", ""),
            model=self.settings.ai_model,
            provider=self.name,
        )
