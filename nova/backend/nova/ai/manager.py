"""AI provider factory and manager."""

from __future__ import annotations

import httpx

from nova.ai.compatible_provider import CompatibleAPIProvider
from nova.ai.local_provider import LocalProvider
from nova.ai.ollama_provider import OllamaProvider
from nova.ai.openai_provider import OpenAIProvider
from nova.ai.provider import AIProvider, AIMessage, AIResponse
from nova.core.config import get_settings
from nova.core.logging import get_logger

logger = get_logger("nova.ai.manager")

PROVIDERS: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "local": LocalProvider,
    "compatible": CompatibleAPIProvider,
}


class AIProviderManager:
    def __init__(self):
        self.settings = get_settings()
        self._instances: dict[str, AIProvider] = {}

    def get_provider(self, name: str | None = None) -> AIProvider:
        provider_name = name or self.settings.ai_provider
        if provider_name not in self._instances:
            cls = PROVIDERS.get(provider_name, LocalProvider)
            self._instances[provider_name] = cls()
        return self._instances[provider_name]

    async def check_network(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.get("https://www.google.com/generate_204")
            return True
        except Exception:
            return False

    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        force_local: bool = False,
    ) -> AIResponse:
        if force_local or self.settings.offline_mode:
            return await self.get_provider("local").chat(messages, system)

        provider = self.get_provider()
        if await provider.is_available():
            try:
                return await provider.chat(messages, system)
            except Exception as e:
                logger.warning("Primary provider failed, falling back to local: %s", e)

        return await self.get_provider("local").chat(messages, system)

    async def health_check(self) -> list[dict]:
        results = []
        for name in PROVIDERS:
            provider = self.get_provider(name)
            results.append(await provider.health_check())
        network = await self.check_network()
        results.append({
            "provider": "network",
            "available": network,
            "status": "PASS" if network else "WARNING",
        })
        return results

    def list_providers(self) -> list[str]:
        return list(PROVIDERS.keys())


_manager: AIProviderManager | None = None


def get_ai_manager() -> AIProviderManager:
    global _manager
    if _manager is None:
        _manager = AIProviderManager()
    return _manager
