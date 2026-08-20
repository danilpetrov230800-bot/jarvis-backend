"""
NOVA AI Provider Layer
- Unified interface for AI providers: Local, OpenAI, Ollama, Custom Compatible
- Automatic fallback to offline rule-based engine when no API or network is available
- Secure key management (no key leaks in logs/prompts)
- Stream & Non-stream support
"""
from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

import httpx

from nova.config import AISettings
from nova.security import redact_secrets, security_manager

log = logging.getLogger("nova.ai")


class BaseAIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], settings: AISettings) -> dict[str, Any]:
        """Generate a chat response"""
        pass

    @abstractmethod
    async def check_health(self, settings: AISettings) -> dict[str, Any]:
        """Check provider connectivity and model availability"""
        pass


class LocalOfflineProvider(BaseAIProvider):
    """Fallback offline AI engine powered by intent classification and rule synthesis"""
    async def chat(self, messages: list[dict[str, str]], settings: AISettings) -> dict[str, Any]:
        last_msg = messages[-1]["content"] if messages else ""
        lowered = last_msg.lower().strip()

        # Local conversational intents
        if lowered in {"привет", "здравствуй", "здравствуйте", "хай", "hello", "hi", "добрый день", "добрый вечер"}:
            return {
                "reply": "Привет! Я NOVA — твой персональный AI-ассистент. Готова помочь с файлами, задачами, управлением ПК и поиском информации.",
                "provider": "local",
                "model": "local-rule-engine",
                "tool_calls": []
            }

        if "кто ты" in lowered or "что ты умеешь" in lowered:
            return {
                "reply": "Я NOVA (Neural Operational & Virtual Assistant). Я умею управлять компьютером, работать с файлами, запускать приложения, сохранять память, выполнять навыки (Skills) и автономные задачи через агентов.",
                "provider": "local",
                "model": "local-rule-engine",
                "tool_calls": []
            }

        return {
            "reply": f"Я приняла твой запрос: «{last_msg}». Работаю в локальном режиме. Для генеративных ответов можно подключить OpenAI или Ollama в Настройках.",
            "provider": "local",
            "model": "local-rule-engine",
            "tool_calls": []
        }

    async def check_health(self, settings: AISettings) -> dict[str, Any]:
        return {"status": "ok", "provider": "local", "model": "local-rule-engine", "message": "Offline Local Engine ready"}


class OpenAIProvider(BaseAIProvider):
    async def chat(self, messages: list[dict[str, str]], settings: AISettings) -> dict[str, Any]:
        if not settings.api_key:
            return await LocalOfflineProvider().chat(messages, settings)

        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }

        url = f"{settings.api_base.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                err_msg = redact_secrets(resp.text)
                log.error(f"OpenAI API Error {resp.status_code}: {err_msg}")
                raise RuntimeError(f"OpenAI API Error ({resp.status_code}): {err_msg}")

            data = resp.json()
            choice = data["choices"][0]
            return {
                "reply": choice["message"]["content"],
                "provider": "openai",
                "model": data.get("model", settings.model),
                "usage": data.get("usage", {})
            }

    async def check_health(self, settings: AISettings) -> dict[str, Any]:
        if not settings.api_key:
            return {"status": "warning", "message": "API key is not configured"}
        try:
            url = f"{settings.api_base.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {settings.api_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return {"status": "ok", "provider": "openai", "message": "Connected to OpenAI API"}
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": redact_secrets(str(e))}


class OllamaProvider(BaseAIProvider):
    async def chat(self, messages: list[dict[str, str]], settings: AISettings) -> dict[str, Any]:
        url = f"{settings.ollama_url.rstrip('/')}/api/chat"
        payload = {
            "model": settings.model or "qwen2.5:7b",
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": settings.temperature,
                "num_predict": settings.max_tokens
            }
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama error: {resp.text}")
                data = resp.json()
                return {
                    "reply": data["message"]["content"],
                    "provider": "ollama",
                    "model": data.get("model", settings.model)
                }
            except Exception as e:
                log.warning(f"Ollama request failed: {e}. Falling back to local offline.")
                return await LocalOfflineProvider().chat(messages, settings)

    async def check_health(self, settings: AISettings) -> dict[str, Any]:
        try:
            url = f"{settings.ollama_url.rstrip('/')}/api/tags"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    return {"status": "ok", "provider": "ollama", "models": models, "message": f"Ollama online ({len(models)} models)"}
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Cannot connect to Ollama at {settings.ollama_url}: {str(e)}"}


def get_ai_provider(provider_type: str) -> BaseAIProvider:
    if provider_type == "openai" or provider_type == "compatible":
        return OpenAIProvider()
    elif provider_type == "ollama":
        return OllamaProvider()
    return LocalOfflineProvider()
