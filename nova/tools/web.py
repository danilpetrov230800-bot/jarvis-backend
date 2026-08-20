from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from nova.tools.base import ToolResult

TIMEOUT = 12.0


async def web_search(query: str = "", max_results: int = 6, region: str = "ru-ru", **_: Any) -> ToolResult:
    if not query:
        return ToolResult(False, "Нужен поисковый запрос.")
    results: list[dict[str, str]] = []
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            for item in ddgs.text(query, region=region, max_results=max_results) or []:
                results.append(
                    {
                        "title": item.get("title") or "",
                        "url": item.get("href") or item.get("url") or "",
                        "snippet": item.get("body") or item.get("snippet") or "",
                    }
                )
    except Exception:
        results = []
    if not results:
        return ToolResult(True, f"По запросу «{query}» ничего не нашла в открытом интернете.", {"results": []})
    lines = [f"По запросу «{query}»:"]
    for item in results[:5]:
        lines.append(f"— {item['title']}: {item['snippet']}")
    return ToolResult(True, "\n".join(lines), {"results": results}, sources=results)


async def browse_url(url: str = "", **_: Any) -> ToolResult:
    if not url.startswith("http"):
        url = "https://" + url
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "NOVA/1.0"}) as client:
        response = await client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = (soup.title.string or url).strip() if soup.title else url
        text = " ".join(soup.get_text(" ").split())[:4000]
    return ToolResult(True, f"{title}\n{text}", {"title": title, "url": str(response.url)}, sources=[{"title": title, "url": str(response.url)}])


async def get_weather(location: str = "Москва", **_: Any) -> ToolResult:
    city = location.strip() or "Москва"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "ru"},
        )
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            return ToolResult(False, f"Не нашла город «{city}».")
        place = results[0]
        weather = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current_weather": True,
                "timezone": "auto",
            },
        )
        weather.raise_for_status()
        current = weather.json().get("current_weather") or {}
        temp = current.get("temperature")
        wind = current.get("windspeed")
        name = place.get("name") or city
        reply = f"В городе {name} сейчас {temp}°C, ветер {wind} км/ч."
        url = f"https://open-meteo.com/"
        return ToolResult(True, reply, current, sources=[{"title": "Open-Meteo", "url": url}])


async def get_currency(**_: Any) -> ToolResult:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        response.raise_for_status()
        valute = response.json().get("Valute") or {}
        usd = valute.get("USD", {}).get("Value")
        eur = valute.get("EUR", {}).get("Value")
        cny = valute.get("CNY", {}).get("Value")
        reply = f"Курс ЦБ: доллар {usd}, евро {eur}, юань {cny}."
        return ToolResult(True, reply, {"USD": usd, "EUR": eur, "CNY": cny}, sources=[{"title": "ЦБ РФ", "url": "https://www.cbr-xml-daily.ru/"}])


async def wiki_summary(topic: str = "", **_: Any) -> ToolResult:
    if not topic:
        return ToolResult(False, "Нужна тема.")
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        response = await client.get(
            "https://ru.wikipedia.org/api/rest_v1/page/summary/" + quote_plus(topic.replace(" ", "_")),
            headers={"User-Agent": "NOVA/1.0"},
        )
        if response.status_code >= 400:
            return ToolResult(False, "Нет статьи в Википедии.")
        data = response.json()
        extract = data.get("extract") or ""
        url = (data.get("content_urls") or {}).get("desktop", {}).get("page") or ""
        return ToolResult(True, extract or "Пустая статья.", data, sources=[{"title": data.get("title") or topic, "url": url}])
