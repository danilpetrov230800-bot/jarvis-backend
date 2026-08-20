from __future__ import annotations

from nova.ai.base import AIProvider, ChatMessage
from nova.ai.local import LocalProvider
from nova.ai.openai_compat import OllamaProvider, OpenAICompatibleProvider
from nova.settings import SettingsService


class ProviderRouter:
    def __init__(self, settings: SettingsService) -> None:
        self.settings = settings

    def current(self) -> AIProvider:
        name = self.settings.resolved_provider()
        if name == "ollama":
            return OllamaProvider(
                base_url=self.settings.resolved_base_url() or "http://127.0.0.1:11434/v1",
                model=self.settings.resolved_model(),
            )
        if name in {"openai", "compatible"}:
            return OpenAICompatibleProvider(
                api_key=self.settings.api_key(),
                base_url=self.settings.resolved_base_url() or "https://api.openai.com/v1",
                model=self.settings.resolved_model(),
                timeout=self.settings.current.ai_timeout_sec,
            )
        return LocalProvider()

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None):
        provider = self.current()
        try:
            return await provider.chat(
                messages,
                tools=tools,
                timeout=self.settings.current.ai_timeout_sec,
            )
        except Exception:
            if provider.name != "local":
                fallback = LocalProvider()
                result = await fallback.chat(messages)
                result.text = (
                    "Внешняя модель недоступна, продолжаю локально.\n\n" + result.text
                )
                return result
            raise
