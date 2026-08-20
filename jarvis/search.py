from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

TRACKING_HOSTS = {
    "googleadservices.com",
    "doubleclick.net",
}


def _ddgs():
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover - old package name
        from duckduckgo_search import DDGS
    return DDGS()


def search_web(query: str, max_results: int = 8, region: str = "wt-wt") -> list[dict[str, str]]:
    """Search the open web. SafeSearch is off on purpose: no extra query filter."""
    query = query.strip()
    if not query:
        return []

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    with _ddgs() as client:
        raw = client.text(
            query,
            region=region,
            safesearch="off",
            max_results=max(max_results * 2, 8),
        )
        for item in raw or []:
            url = (item.get("href") or item.get("url") or "").strip()
            if not url or url in seen:
                continue
            host = urlparse(url).netloc.lower()
            if any(bad in host for bad in TRACKING_HOSTS):
                continue
            seen.add(url)
            results.append(
                {
                    "title": (item.get("title") or "").strip(),
                    "url": url,
                    "snippet": (item.get("body") or item.get("snippet") or "").strip(),
                }
            )
            if len(results) >= max_results:
                break
    return results


def html_to_text(html: str, limit: int = 8000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav", "form"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


async def browse_url(url: str, limit: int = 8000) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "json" not in content_type and "html" not in content_type:
            return {"url": str(response.url), "title": "", "text": f"Нетекствый ответ: {content_type}"}
        html = response.text
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    return {"url": str(response.url), "title": title, "text": html_to_text(html, limit=limit)}


def format_search_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "Поиск не дал результатов."
    lines = []
    for i, item in enumerate(results, start=1):
        lines.append(f"{i}. {item.get('title') or 'Без названия'}\n   {item.get('url')}\n   {item.get('snippet')}")
    return "\n".join(lines)


def serialize_sources(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    sources = []
    for item in results:
        sources.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
            }
        )
    return sources
