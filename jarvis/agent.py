from __future__ import annotations

import asyncio
from typing import Any

from jarvis.files_agent import handle_file_intent
from jarvis.search import search_web, serialize_sources
from jarvis.services import wiki_summary

MAX_STEPS = 8
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY = 2


async def run_agent(
    query: str,
    region: str = "ru-ru",
    timeout: float = DEFAULT_TIMEOUT,
    retry_limit: int = DEFAULT_RETRY,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async def body() -> dict[str, Any]:
        return await _run(query, region, retry_limit, agent)

    try:
        return await asyncio.wait_for(body(), timeout=max(1.0, timeout))
    except TimeoutError:
        return {
            "reply": "Агент остановлен: превышено время ожидания.",
            "tools": ["agent"],
            "sources": [],
            "steps": ["Планирую задачу", "Таймаут"],
        }


async def _run(
    query: str,
    region: str,
    retry_limit: int,
    agent: dict[str, Any] | None,
) -> dict[str, Any]:
    steps: list[str] = []
    sources: list[dict[str, str]] = []
    parts: list[str] = []
    if len(query) > 4000:
        query = query[:4000]
    role = (agent or {}).get("name") or "NOVA"
    steps.append(f"Планирую задачу ({role})")
    allowed_tools = set((agent or {}).get("tools") or ["search", "wiki", "files", "system"])
    if "files" in allowed_tools:
        file_hit = handle_file_intent(query)
        if file_hit:
            steps.append("Ищу файлы")
            parts.append(str(file_hit.get("reply")))
    need_web = any(word in query.lower() for word in ("что такое", "найди", "сравни", "информац", "вариант"))
    if need_web and ("search" in allowed_tools or "wiki" in allowed_tools):
        results: list[dict[str, str]] = []
        last_error = ""
        for attempt in range(max(1, retry_limit + 1)):
            try:
                steps.append("Ищу в открытых источниках" if attempt == 0 else f"Повтор поиска {attempt}")
                results = search_web(query, max_results=5, region=region)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt >= retry_limit:
                    steps.append("Поиск недоступен")
                    parts.append("Сеть не ответила. Работаю с тем, что есть локально.")
        sources.extend(serialize_sources(results))
        if results:
            parts.append("Источники: " + "; ".join(item.get("title") or item.get("url") or "" for item in results[:4]))
        if "wiki" in allowed_tools:
            topic = query.replace("найди", "").replace("сравни", "").strip()
            try:
                wiki = await wiki_summary(topic[:80] or query[:80])
                parts.append(wiki["reply"][:600])
                sources.append({"title": wiki["title"], "url": wiki["url"]})
                steps.append("Проверяю результат")
            except Exception:
                steps.append("Википедия недоступна, оставляю поиск")
        if last_error and not results:
            parts.append("Проверка: открытые источники сейчас недоступны.")
    if "system" in allowed_tools and any(word in query.lower() for word in ("компьютер", "система", "тормозит")):
        from jarvis.desktop import system_info

        steps.append("Смотрю систему")
        parts.append(system_info())
    steps.append("Готово")
    if len(steps) > MAX_STEPS:
        steps = steps[: MAX_STEPS - 1] + ["Готово"]
    reply = "\n".join(parts) if parts else "Не хватило данных, чтобы выполнить задачу."
    if agent and agent.get("instructions"):
        reply = f"{agent['name']}: {reply}"
    return {"reply": reply, "tools": ["agent"], "sources": sources, "steps": steps}
