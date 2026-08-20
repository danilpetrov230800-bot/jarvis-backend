from __future__ import annotations

from typing import Any

from nova.ai.base import AIProvider, ChatMessage, ProviderResult
from nova.errors import ProviderError


class OpenAICompatibleProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 45) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        timeout: float = 45,
    ) -> ProviderResult:
        if not self.api_key:
            raise ProviderError("API-ключ не задан.")
        try:
            from openai import AsyncOpenAI
        except Exception as exc:  # pragma: no cover
            raise ProviderError("Модуль OpenAI недоступен.") from exc

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout or self.timeout)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.6,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            response = await client.chat.completions.create(**payload)
        except Exception as exc:
            raise ProviderError("Не удалось получить ответ модели.") from exc
        choice = response.choices[0]
        message = choice.message
        tool_calls = []
        for call in getattr(message, "tool_calls", None) or []:
            tool_calls.append(
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                }
            )
        return ProviderResult(
            text=(message.content or "").strip(),
            provider=self.name,
            model=self.model,
            tool_calls=tool_calls,
        )

    async def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "ok": bool(self.api_key),
            "model": self.model,
            "base_url": self.base_url,
        }


class OllamaProvider(OpenAICompatibleProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434/v1", model: str = "llama3.2") -> None:
        super().__init__(api_key="ollama", base_url=base_url, model=model)
