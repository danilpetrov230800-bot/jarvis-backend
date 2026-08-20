from __future__ import annotations

import logging
import re
from typing import Any

from jarvis.apps import launch_named
from jarvis.config import Settings
from jarvis.desktop import ActionResult, handle_intent, help_text
from jarvis.files_agent import handle_file_intent
from jarvis.llm import LLMError, chat_once
from jarvis.memory_long import add_memory, recall_text
from jarvis.pc_control import handle_pc_intent
from jarvis.prompts import search_needed
from jarvis.search import serialize_sources, search_web
from jarvis.skills import create_skill, match_skill
from jarvis import services

WEATHER_RE = re.compile(r"погод[аеуы]?\s*(?:в\s+)?(.+)?$", re.I)
QUESTION_RE = re.compile(r"^(кто|что|где|когда|почему|зачем|как|сколько|какой|какая|какое)\b", re.I)
GOOGLE_RE = re.compile(r"^(?:погугли|загугли|гугли|google)\s+(.+)$", re.I)
CURRENCY_RE = re.compile(r"курс|валют|\bдоллар|\bевро\b|\bюан", re.I)
GREETINGS = {"привет", "здравствуй", "здравствуйте", "хай", "hello", "hi", "добрый день", "добрый вечер"}

log = logging.getLogger(__name__)


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
    return services.normalize_place(city)


def _clean(text: str) -> str:
    return text.strip().lower().strip(" .!?…")


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
            return services.normalize_place(leftover)
    return "Москва"


async def respond(settings: Settings, history: list[dict[str, Any]], text: str) -> dict[str, Any]:
    lowered = _clean(text)
    if lowered in GREETINGS:
        return _pack("Привет. Я Nova. Могу открыть сайт, прибавить звук, сказать пробки и погоду — без ключа.")

    if lowered.startswith("запомни"):
        content = re.sub(r"^запомни[,:\s]*(что\s+)?", "", text.strip(), flags=re.I).strip()
        if content:
            item = add_memory(content, kind="note")
            return _pack(f"Запомнила: {item['content']}", tools=["memory"])

    if lowered in {"что ты помнишь", "что помнишь", "вспомни"} or lowered.startswith("вспомни "):
        query = re.sub(r"^вспомни\s+", "", lowered)
        if query in {"что ты помнишь", "что помнишь", "вспомни"}:
            query = ""
        return _pack(recall_text(query), tools=["memory"])

    if lowered.startswith("всегда делай") or lowered.startswith("всегда "):
        content = re.sub(r"^всегда (делай[,:\s]*)?", "", text.strip(), flags=re.I).strip()
        if content:
            item = add_memory(content, kind="preference")
            return _pack(f"Сохранила предпочтение: {item['content']}", tools=["memory"])

    learn = re.match(r"^научись делать\s+(.+)$", text.strip(), re.I)
    if learn:
        skill = create_skill(learn.group(1), learn.group(1), action_text=learn.group(1))
        return _pack(f"Навык сохранён. Триггер: {skill['trigger_text']}.", tools=["skill"])

    skill_make = re.match(
        r"когда я говорю\s+[«\"']?(.+?)[»\"']?\s*,\s*(.+)$",
        text.strip(),
        re.I,
    )
    if skill_make:
        skill = create_skill(skill_make.group(1), skill_make.group(1), action_text=skill_make.group(2))
        return _pack(f"Навык сохранён. Триггер: {skill['trigger_text']}.", tools=["skill"])

    matched = match_skill(text)
    if matched:
        return _from_action(matched)

    if lowered.startswith("агент ") or lowered.startswith("выполни задачу") or lowered.startswith("задача:") or lowered.startswith("поручи "):
        from jarvis.agent import run_agent
        from jarvis.agents_catalog import find_agent

        query = re.sub(r"^(агент|выполни задачу|задача:|поручи)\s*", "", text.strip(), flags=re.I)
        specialist = None
        named = re.match(r"^([A-Za-zА-Яа-я]+)\s*[:\-]\s*(.+)$", query)
        if named:
            specialist = find_agent(named.group(1))
            if specialist:
                query = named.group(2)
        return _pack(**(await run_agent(query, region=settings.search_region, agent=specialist)))

    if lowered.startswith("исследуй ") or lowered.startswith("research "):
        from jarvis.research import research as do_research

        query = re.sub(r"^(исследуй|research)\s+", "", text.strip(), flags=re.I)
        try:
            data = await do_research(query, region=settings.search_region)
            return _pack(str(data["reply"]), tools=list(data.get("tools") or ["research"]), sources=list(data.get("sources") or []))
        except PermissionError as exc:
            return _pack(str(exc), tools=["permission"])

    try:
        file_hit = handle_file_intent(text)
    except PermissionError as exc:
        return _pack(str(exc), tools=["permission"])
    if file_hit:
        return _pack(str(file_hit["reply"]), tools=list(file_hit.get("tools") or ["files"]))

    if any(p in lowered for p in ("посмотри на экран", "что на экране", "посмотри экран", "что произошло")):
        from jarvis.desktop import describe_screen

        return _pack(describe_screen(), tools=["screen"])

    if any(p in lowered for p in ("что с компьютер", "тормозит", "что происходит с компьютер", "состояние пк")):
        from jarvis.desktop import diagnose_machine

        return _pack(diagnose_machine(), tools=["system_info"])

    pc = handle_pc_intent(lowered)
    if pc:
        return _pack(pc.reply, tools=pc.tools)

    action = handle_intent(text)
    if action and "open_unknown" in action.tools:
        name_match = re.search(r"«(.+?)»", action.reply)
        if name_match:
            launched = launch_named(name_match.group(1))
            if not launched.startswith("Не нашла"):
                return _pack(launched, tools=["open_app"])
    if action and "open_unknown" not in action.tools:
        return _from_action(action)

    city = _city_from(text)
    try:
        if lowered in {"мой ip", "мой айпи", "ip", "айпи", "внешний ip"}:
            data = await services.get_public_ip()
            return _pack(data["reply"], tools=["ip"], sources=[{"title": data["title"], "url": data["url"]}])
        if "пробк" in lowered:
            data = await services.get_traffic(_place_after(text, "пробки", "пробка"))
            return _pack(str(data["reply"]), tools=["traffic"], sources=list(data.get("sources") or []))
        if "погод" in lowered:
            data = await services.get_weather(city)
            return _pack(data["reply"], tools=["weather"], sources=[{"title": data["title"], "url": data["url"]}])
        if "воздух" in lowered or "смог" in lowered:
            data = await services.get_air(_place_after(text, "воздух", "смог"))
            return _pack(data["reply"], tools=["air"], sources=[{"title": data["title"], "url": data["url"]}])
        if CURRENCY_RE.search(lowered):
            data = await services.get_currency()
            return _pack(data["reply"], tools=["currency"], sources=[{"title": data["title"], "url": data["url"]}])
        if lowered in {"новости", "что нового"} or "новост" in lowered:
            data = await services.get_news()
            return _pack(str(data["reply"]), tools=["news"], sources=list(data.get("sources") or []))
        if lowered.startswith("переведи ") or lowered.startswith("translate "):
            target = "en" if re.search(r"на\s+англий|into english|to english", lowered) else "ru"
            phrase = re.sub(r"^(переведи|translate)\s+", "", text.strip(), flags=re.I)
            phrase = re.sub(r"\s+на\s+(английский|русский|english|russian)\s*$", "", phrase, flags=re.I)
            data = await services.translate_text(phrase, target=target)
            return _pack(data["reply"], tools=["translate"], sources=[{"title": data["title"], "url": data["url"]}])
    except Exception:
        log.exception("online service failed, falling back")

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
