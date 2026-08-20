from __future__ import annotations

import re
from typing import Any

from jarvis.config import Settings
from jarvis.desktop import ActionResult, handle_intent, help_text
from jarvis.llm import LLMError, chat_once
from jarvis.pc_control import handle_pc_intent
from jarvis.prompts import search_needed
from jarvis.search import serialize_sources, search_web
from jarvis import services

WEATHER_RE = re.compile(r"погод[аеуы]?\s*(?:в\s+)?(.+)?$", re.I)
QUESTION_RE = re.compile(r"^(кто|что|где|когда|почему|зачем|как|сколько|какой|какая|какое)\b", re.I)
GOOGLE_RE = re.compile(r"^(?:погугли|загугли|гугли|google)\s+(.+)$", re.I)


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


def _place_after(text: str, *needles: str) -> str:
    lowered = text.lower()
    for needle in needles:
        if needle in lowered:
            leftover = lowered.split(needle, 1)[-1]
            leftover = re.sub(r"^(в|на|по)\s+", "", leftover.strip(" ?!."))
            return leftover or "Москва"
    return "Москва"


async def respond(settings: Settings, history: list[dict[str, Any]], text: str) -> dict[str, Any]:
    lowered = text.strip().lower()
    if lowered in {"привет", "здравствуй", "здравствуйте", "хай", "hello", "hi"}:
        return _pack("Привет. Я Nova. Могу открыть сайт, прибавить звук, сказать пробки и погоду — без ключа.")

    pc = handle_pc_intent(lowered)
    if pc:
        return _pack(pc.reply, tools=pc.tools)

    action = handle_intent(text)
    if action and "open_unknown" not in action.tools:
        return _from_action(action)

    city = _city_from(text)
    try:
        if "пробк" in lowered:
            data = await services.get_traffic(_place_after(text, "пробки", "пробка"))
            return _pack(str(data["reply"]), tools=["traffic"], sources=list(data.get("sources") or []))
        if "погод" in lowered:
            data = await services.get_weather(city)
            return _pack(data["reply"], tools=["weather"], sources=[{"title": data["title"], "url": data["url"]}])
        if "воздух" in lowered or "смог" in lowered:
            data = await services.get_air(_place_after(text, "воздух", "смог") if city == "Москва" else city)
            return _pack(data["reply"], tools=["air"], sources=[{"title": data["title"], "url": data["url"]}])
        if "курс" in lowered or "доллар" in lowered or "евро" in lowered:
            data = await services.get_currency()
            return _pack(data["reply"], tools=["currency"], sources=[{"title": data["title"], "url": data["url"]}])
        if lowered in {"новости", "что нового"} or "новост" in lowered:
            data = await services.get_news()
            return _pack(str(data["reply"]), tools=["news"], sources=list(data.get("sources") or []))
        if lowered.startswith("переведи ") or lowered.startswith("translate "):
            phrase = re.sub(r"^(переведи|translate)\s+", "", text.strip(), flags=re.I)
            data = await services.translate_text(phrase)
            return _pack(data["reply"], tools=["translate"], sources=[{"title": data["title"], "url": data["url"]}])
    except Exception as exc:  # noqa: BLE001
        return _pack(f"Сервис временно недоступен: {exc}. Поищу в сети.", tools=["service_error"])

    if lowered.startswith("вики ") or lowered.startswith("что такое "):
        topic = re.sub(r"^(вики|что такое)\s+", "", text.strip(), flags=re.I)
        try:
            data = await services.wiki_summary(topic)
            if data.get("reply") and "Нет статьи" not in data["reply"]:
                return _pack(data["reply"], tools=["wiki"], sources=[{"title": data["title"], "url": data["url"]}])
        except Exception:
            pass

    google = GOOGLE_RE.match(text.strip())
    if google:
        query = google.group(1).strip()
        results = search_web(query, region=settings.search_region)
        return _pack(
            summarize_search(query, results),
            tools=["web_search"],
            sources=serialize_sources(results),
        )

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
