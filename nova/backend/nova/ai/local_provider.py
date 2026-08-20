"""Local rule-based AI provider for offline mode."""

from __future__ import annotations

import re

from nova.ai.provider import AIMessage, AIProvider, AIResponse
from nova.core.logging import get_logger

logger = get_logger("nova.ai.local")

SYSTEM_PROMPT = (
    "Ты NOVA — персональный AI-ассистент. "
    "Отвечай по-русски, естественно и полезно."
)


class LocalProvider(AIProvider):
    name = "local"

    async def is_available(self) -> bool:
        return True

    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        if not messages:
            return AIResponse(
                content="Привет! Я NOVA. Чем могу помочь?",
                model="local",
                provider=self.name,
            )

        text = messages[-1].content.lower().strip()

        if any(w in text for w in ("привет", "здравств", "hello", "hi")):
            reply = "Привет! Я NOVA, ваш персональный ассистент. Чем могу помочь?"
        elif "время" in text or "который час" in text:
            from datetime import datetime
            now = datetime.now().strftime("%H:%M")
            reply = f"Сейчас {now}."
        elif "дата" in text or "какое число" in text:
            from datetime import datetime
            now = datetime.now().strftime("%d.%m.%Y")
            reply = f"Сегодня {now}."
        elif re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", text):
            expr = re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", text)
            if expr:
                try:
                    result = eval(expr.group(1), {"__builtins__": {}}, {})
                    reply = f"Результат: {result}"
                except Exception:
                    reply = "Не удалось вычислить выражение."
            else:
                reply = "Укажите математическое выражение."
        elif "offline" in text or "офлайн" in text or "интернет" in text:
            reply = "Я работаю в локальном режиме. Основные функции доступны без интернета."
        elif "помощ" in text or "help" in text:
            reply = (
                "Я могу: отвечать на вопросы, выполнять расчёты, управлять файлами, "
                "запускать приложения, запоминать информацию и выполнять Skills. "
                "Скажите «Нова» для голосовых команд."
            )
        else:
            reply = (
                "Я работаю в локальном режиме без подключения к облачной модели. "
                "Для расширенных возможностей настройте AI-провайдер в Settings → AI. "
                f"Ваш запрос: «{messages[-1].content}»"
            )

        return AIResponse(content=reply, model="local", provider=self.name)
