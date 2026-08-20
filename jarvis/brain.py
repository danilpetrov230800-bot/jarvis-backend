from __future__ import annotations

import re
from typing import Any

from jarvis.config import Settings
from jarvis.desktop import ActionResult, handle_intent, help_text
from jarvis.llm import LLMError, chat_once
from jarvis.prompts import search_needed
from jarvis.search import format_search_results, search_web, serialize_sources
from jarvis.tools import ToolContext, tool_get_weather

WEATHER_RE = re.compile(r"погод[аеуы]?\s*(?:в\s+)?(.+)?$", re.I)
QUESTION_RE = re.compile(r"^(кто|что|где|когда|почему|зачем|как|сколько|какой|какая|какое)\b", re.I)


def _pack(reply: str, tools: list[str] | None = None, sources: list[dict[str, str]] | None = None, **extra: Any) -> dict[str, Any]:
    payload = {
        "reply": reply,
        "sources": sources or [],
        "tools": tools or [],
        "model": extra.get("model", "nova-local"),
        "provider": extra.get("provider", "local"),
    }
    payload.update(extra)
    return payload


def _from_action(action: ActionResult) -> dict[str, Any]:
    return _pack(action.reply, tools=action.tools, sources=action.sources)


def _city_from(text: str) -> str:
    match = WEATHER_RE.search(text.strip())
    city = (match.group(1) or "").strip(" .!?") if match else ""
    return city or "Москва"


def summarize_search(query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return f"По запросу «{query}» в открытом интернете ничего не нашла."
    lines = [f"По запросу «{query}» вот что есть в сети:"]
    for item in results[:5]:
        title = item.get("title") or "Источник"
        snippet = (item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"— {title}: {snippet}")
        else:
            lines.append(f"— {title}")
    return "\n".join(lines)


async def respond(settings: Settings, history: list[dict[str, Any]], text: str) -> dict[str, Any]:
    lowered = text.strip().lower()
    if lowered in {"привет", "здравствуй", "здравствуйте", "хай", "hello", "hi"}:
        return _pack("Привет. Я Nova. Могу открыть сайт или программу, поискать в сети, сказать время и погоду — ключ для этого не нужен.")

    action = handle_intent(text)
    if action and "open_unknown" not in action.tools:
        return _from_action(action)

    if "погод" in lowered:
        ctx = ToolContext(region=settings.search_region)
        report = await tool_get_weather(ctx, _city_from(text))
        return _pack(report, tools=["weather"], sources=ctx.sources)

    can_llm = bool(settings.api_key) or settings.provider == "ollama"
    if can_llm:
        try:
            return await chat_once(settings, history, text)
        except LLMError:
            pass

    if search_needed(text) or QUESTION_RE.search(text.strip()) or "погугл" in lowered:
        results = search_web(text, region=settings.search_region)
        return _pack(
            summarize_search(text, results),
            tools=["web_search"],
            sources=serialize_sources(results),
        )

    if action:
        return _from_action(action)

    return _pack(help_text(), tools=["help"])
