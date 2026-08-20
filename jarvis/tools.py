from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from zoneinfo import ZoneInfo

import httpx

from jarvis.desktop import open_app, open_url, save_note, take_screenshot
from jarvis.search import browse_url, format_search_results, search_web, serialize_sources

ToolHandler = Callable[..., Awaitable[str]]


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Искать в открытом интернете без фильтра безопасного поиска. "
                "Используй для фактов, новостей, цен, людей, инструкций, кода, науки."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на языке источника или на русском.",
                    },
                    "max_results": {"type": "integer", "description": "Сколько результатов вернуть, 3–10."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Открыть страницу по URL и прочитать её текст.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Полный URL страницы."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Текущие дата и время. Часовой пояс по умолчанию — Europe/Moscow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "IANA timezone, например Europe/Moscow."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Погода через wttr.in. Город можно писать по-русски.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Город или место."},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Открыть сайт в браузере пользователя.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Запустить программу на ПК: notepad, calc, explorer, chrome, steam.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Сделать снимок экрана.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Сохранить заметку.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
]


class ToolContext:
    def __init__(self, region: str = "wt-wt") -> None:
        self.region = region
        self.sources: list[dict[str, str]] = []
        self.log: list[str] = []


async def tool_web_search(ctx: ToolContext, query: str, max_results: int = 8) -> str:
    results = search_web(query, max_results=max_results, region=ctx.region)
    ctx.sources.extend(serialize_sources(results))
    ctx.log.append(f"search:{query}")
    return format_search_results(results)


async def tool_browse_url(ctx: ToolContext, url: str) -> str:
    page = await browse_url(url)
    ctx.sources.append({"title": page.get("title") or url, "url": page.get("url") or url})
    ctx.log.append(f"browse:{url}")
    title = page.get("title") or "без названия"
    return f"Страница: {title}\nURL: {page.get('url')}\n\n{page.get('text')}"


async def tool_get_datetime(ctx: ToolContext, timezone: str = "Europe/Moscow") -> str:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
        timezone = "Europe/Moscow"
    now = datetime.now(tz)
    ctx.log.append("datetime")
    return now.strftime(f"%A, %d %B %Y, %H:%M:%S ({timezone}, UTC{now.strftime('%z')})")


async def tool_get_weather(ctx: ToolContext, location: str) -> str:
    url = f"https://wttr.in/{location}?format=j1&lang=ru"
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "jarvis-assistant"})
        response.raise_for_status()
        data = response.json()
    current = data.get("current_condition", [{}])[0]
    nearest = (data.get("nearest_area") or [{}])[0]
    place = ""
    if nearest.get("areaName"):
        place = nearest["areaName"][0].get("value", location)
    ctx.sources.append({"title": f"Погода: {place or location}", "url": f"https://wttr.in/{location}"})
    ctx.log.append(f"weather:{location}")
    desc = ""
    langs = current.get("lang_ru") or current.get("weatherDesc") or []
    if langs:
        desc = langs[0].get("value", "")
    return (
        f"Место: {place or location}\n"
        f"Сейчас: {current.get('temp_C')}°C, ощущается как {current.get('FeelsLikeC')}°C\n"
        f"Описание: {desc}\n"
        f"Ветер: {current.get('windspeedKmph')} км/ч, влажность {current.get('humidity')}%"
    )


async def tool_open_url(ctx: ToolContext, url: str) -> str:
    opened = open_url(url)
    ctx.log.append(f"open_url:{opened}")
    ctx.sources.append({"title": opened, "url": opened})
    return f"Открыто: {opened}"


async def tool_open_app(ctx: ToolContext, name: str) -> str:
    launched = open_app(name)
    ctx.log.append(f"open_app:{name}")
    if launched:
        return f"Запущено: {launched}"
    return f"Не нашла программу «{name}»."


async def tool_take_screenshot(ctx: ToolContext) -> str:
    path = take_screenshot()
    ctx.log.append("screenshot")
    return f"Скриншот: {path}"


async def tool_save_note(ctx: ToolContext, text: str) -> str:
    path = save_note(text)
    ctx.log.append("note")
    return f"Заметка сохранена: {path}"


HANDLERS: dict[str, Any] = {
    "web_search": tool_web_search,
    "browse_url": tool_browse_url,
    "get_datetime": tool_get_datetime,
    "get_weather": tool_get_weather,
    "open_url": tool_open_url,
    "open_app": tool_open_app,
    "take_screenshot": tool_take_screenshot,
    "save_note": tool_save_note,
}


async def execute_tool(ctx: ToolContext, name: str, arguments: dict[str, Any] | str) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            arguments = {"query": arguments} if name == "web_search" else {}
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Неизвестный инструмент: {name}"
    try:
        return await handler(ctx, **arguments)
    except TypeError as exc:
        return f"Неверные аргументы для {name}: {exc}"
    except Exception as exc:  # noqa: BLE001 — surface tool errors to the model
        return f"Ошибка {name}: {exc}"
