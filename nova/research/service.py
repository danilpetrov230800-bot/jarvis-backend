from __future__ import annotations

from typing import Any
from urllib.parse import quote

from nova.errors import PermissionDenied
from nova.permissions import PermissionService
from nova.tools.base import ToolResult
from nova.tools.web import web_search

PUBLIC_TEMPLATES = {
    "github": "https://github.com/{id}",
    "gitlab": "https://gitlab.com/{id}",
    "telegram": "https://t.me/{id}",
    "vk": "https://vk.com/{id}",
    "youtube": "https://www.youtube.com/@{id}",
    "reddit": "https://www.reddit.com/user/{id}",
    "linkedin": "https://www.linkedin.com/in/{id}",
    "x": "https://x.com/{id}",
}


class ResearchService:
    """Creator-only public OSINT. No auth bypass, captcha, or private data."""

    def __init__(self, permissions: PermissionService) -> None:
        self.permissions = permissions

    def _guard(self) -> None:
        if not self.permissions.allowed("RESEARCH"):
            raise PermissionDenied("Режим исследования выключен.")

    async def search_profiles(self, identifier: str) -> ToolResult:
        self._guard()
        ident = identifier.strip().lstrip("@")
        if not ident or any(ch in ident for ch in " /\\\"'"):
            return ToolResult(False, "Нужен открытый идентификатор, который вам разрешено проверять.")
        links = [
            {"network": name, "url": url.format(id=quote(ident, safe="._-"))}
            for name, url in PUBLIC_TEMPLATES.items()
        ]
        mentions = await web_search(query=f'"{ident}"', max_results=8)
        photos = await web_search(query=f"{ident} site:commons.wikimedia.org OR site:wikipedia.org", max_results=5)
        graph = {
            "identifier": ident,
            "profiles": links,
            "mentions": mentions.data.get("results") or [],
            "photos": photos.data.get("results") or [],
        }
        lines = [f"Открытые ссылки для «{ident}»:"]
        for item in links:
            lines.append(f"- {item['network']}: {item['url']}")
        if mentions.reply:
            lines.append("")
            lines.append("Упоминания в открытом поиске:")
            lines.append(mentions.reply)
        return ToolResult(True, "\n".join(lines), graph, sources=mentions.sources)

    async def analyze(self, query: str) -> ToolResult:
        self._guard()
        result = await web_search(query=query, max_results=10)
        return result
