from __future__ import annotations

from jarvis.permissions import allowed, deny_message
from jarvis.search import search_web, serialize_sources
from jarvis.services import wiki_summary


async def research(query: str, region: str = "ru-ru") -> dict[str, object]:
    if not allowed("RESEARCH"):
        raise PermissionError(deny_message("RESEARCH"))
    text = query.strip()
    if not text:
        raise ValueError("пустой запрос")
    results = search_web(text, max_results=8, region=region)
    sources = serialize_sources(results)
    lines = [f"Открытые источники по запросу «{text}»:"]
    for item in results[:6]:
        title = item.get("title") or "Источник"
        snippet = item.get("snippet") or ""
        lines.append(f"— {title}: {snippet}")
    try:
        wiki = await wiki_summary(text)
        lines.append("Википедия: " + wiki["reply"][:500])
        sources.insert(0, {"title": wiki["title"], "url": wiki["url"]})
    except Exception:
        pass
    if len(lines) == 1:
        lines.append("Публичных результатов мало.")
    return {"reply": "\n".join(lines), "sources": sources, "tools": ["research"]}
