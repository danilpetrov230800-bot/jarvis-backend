"""OpenAI AI provider."""

from __future__ import annotations

import httpx
from openai import AsyncOpenAI

from nova.ai.provider import AIMessage, AIProvider, AIResponse
from nova.core.config import get_settings
from nova.core.logging import get_logger
from nova.security.secrets import get_secret_store

logger = get_logger("nova.ai.openai")


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self):
        self.settings = get_settings()
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI | None:
        key = get_secret_store().get("openai_api_key")
        if not key:
            return None
        if self._client is None:
            self._client = AsyncOpenAI(api_key=key)
        return self._client

    async def is_available(self) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            await client.models.list()
            return True
        except Exception as e:
            logger.warning("OpenAI unavailable: %s", type(e).__name__)
            return False

    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        client = self._get_client()
        if not client:
            raise RuntimeError("OpenAI API key not configured")

        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        kwargs: dict = {
            "model": self.settings.ai_model,
            "messages": api_messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        return AIResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )
