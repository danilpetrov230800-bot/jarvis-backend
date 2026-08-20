from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Awaitable
from zoneinfo import ZoneInfo

from jarvis.desktop import open_app, open_url, save_note, take_screenshot
from jarvis.search import browse_url, format_search_results, search_web, serialize_sources
from jarvis import services

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
            "description": "Текущая погода по городу через Open-Meteo. Город можно писать по-русски.",
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
            "name": "get_traffic",
            "description": "Сводка пробок в городе и ссылка на Яндекс.Карты.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "Город, например Москва."}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_currency",
            "description": "Курс доллара, евро и юаня по данным ЦБ РФ.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Свежие заголовки новостей.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pc_control",
            "description": "Управление ПК: громкость, яркость, пауза медиа. Только Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "volume_up, volume_down, mute, brighter, darker, brightness, play, next, prev",
                    },
                    "value": {"type": "integer", "description": "Яркость 0–100, если action=brightness."},
                },
                "required": ["action"],
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
    data = await services.get_weather(location)
    ctx.sources.append({"title": data["title"], "url": data["url"]})
    ctx.log.append(f"weather:{location}")
    return data["reply"]


async def tool_get_traffic(ctx: ToolContext, city: str) -> str:
    data = await services.get_traffic(city)
    ctx.sources.extend(list(data.get("sources") or []))
    ctx.log.append(f"traffic:{city}")
    return str(data["reply"])


async def tool_get_currency(ctx: ToolContext) -> str:
    data = await services.get_currency()
    ctx.sources.append({"title": data["title"], "url": data["url"]})
    ctx.log.append("currency")
    return data["reply"]


async def tool_get_news(ctx: ToolContext) -> str:
    data = await services.get_news()
    ctx.sources.extend(list(data.get("sources") or []))
    ctx.log.append("news")
    return str(data["reply"])


async def tool_pc_control(ctx: ToolContext, action: str, value: int | None = None) -> str:
    from jarvis import pc_control

    mapping = {
        "volume_up": pc_control.volume_up,
        "volume_down": pc_control.volume_down,
        "mute": pc_control.volume_mute,
        "brighter": pc_control.brightness_up,
        "darker": pc_control.brightness_down,
        "play": pc_control.media_play_pause,
        "next": pc_control.media_next,
        "prev": pc_control.media_prev,
    }
    ctx.log.append(f"pc:{action}")
    if action == "brightness":
        return pc_control.set_brightness(value or 70)
    handler = mapping.get(action)
    if handler is None:
        return f"Неизвестное действие ПК: {action}"
    return handler()


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
    "get_traffic": tool_get_traffic,
    "get_currency": tool_get_currency,
    "get_news": tool_get_news,
    "pc_control": tool_pc_control,
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
