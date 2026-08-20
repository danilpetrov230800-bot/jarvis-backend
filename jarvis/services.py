from __future__ import annotations

from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from jarvis.search import search_web, serialize_sources

HEADERS = {"User-Agent": "NOVA-assistant/1.2"}

CITY_ALIASES = {
    "мск": "Москва",
    "москва": "Москва",
    "москве": "Москва",
    "москвы": "Москва",
    "питер": "Санкт-Петербург",
    "питере": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "петербург": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "екб": "Екатеринбург",
    "екатеринбург": "Екатеринбург",
    "нск": "Новосибирск",
    "новосибирск": "Новосибирск",
    "кзн": "Казань",
    "казань": "Казань",
    "казани": "Казань",
}


def normalize_place(name: str) -> str:
    raw = (name or "").strip(" .!?,")
    if not raw:
        return "Москва"
    return CITY_ALIASES.get(raw.lower(), raw)


async def geocode(city: str) -> dict[str, float | str] | None:
    city = normalize_place(city)
    url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        response = await client.get(url, params={"name": city, "count": 1, "language": "ru"})
        response.raise_for_status()
        data = response.json()
    results = data.get("results") or []
    if not results:
        return None
    item = results[0]
    return {
        "name": item.get("name") or city,
        "lat": float(item["latitude"]),
        "lon": float(item["longitude"]),
        "country": item.get("country") or "",
    }


WMO = {
    0: "ясно",
    1: "почти ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    51: "морось",
    61: "дождь",
    71: "снег",
    80: "ливни",
    95: "гроза",
}


async def get_weather(city: str) -> dict[str, str]:
    place = await geocode(city)
    if not place:
        raise RuntimeError(f"не нашла город «{city}»")
    params = {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone": "Europe/Moscow",
        "wind_speed_unit": "ms",
    }
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        current = response.json().get("current") or {}
    code = int(current.get("weather_code") or 0)
    text = (
        f"Погода в {place['name']}: {current.get('temperature_2m')}°, "
        f"ощущается как {current.get('apparent_temperature')}°, {WMO.get(code, 'переменная погода')}. "
        f"Ветер {current.get('wind_speed_10m')} м/с, влажность {current.get('relative_humidity_2m')}%."
    )
    return {
        "reply": text,
        "title": f"Погода: {place['name']}",
        "url": f"https://open-meteo.com/",
    }


async def get_air(city: str) -> dict[str, str]:
    place = await geocode(city)
    if not place:
        raise RuntimeError(f"не нашла город «{city}»")
    params = {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "current": "pm10,pm2_5,european_aqi",
    }
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        response = await client.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params)
        response.raise_for_status()
        current = response.json().get("current") or {}
    text = (
        f"Воздух в {place['name']}: индекс {current.get('european_aqi')}, "
        f"PM2.5 {current.get('pm2_5')}, PM10 {current.get('pm10')}."
    )
    return {"reply": text, "title": f"Воздух: {place['name']}", "url": "https://open-meteo.com/en/docs/air-quality-api"}


async def get_traffic(city: str) -> dict[str, object]:
    city = normalize_place(city)
    query = f"пробки {city} сейчас"
    results = search_web(query, max_results=5, region="ru-ru")
    maps = f"https://yandex.ru/maps/?l=trf&text={quote(city)}"
    lines = [f"Пробки в {city}:"]
    for item in results[:4]:
        snippet = (item.get("snippet") or "").strip()
        title = item.get("title") or ""
        if snippet:
            lines.append(f"— {title}: {snippet}")
    if len(lines) == 1:
        lines.append("Актуальных сводок мало. Откройте Яндекс.Карты со слоем пробок.")
    lines.append(f"Карта: {maps}")
    sources = serialize_sources(results)
    sources.insert(0, {"title": "Яндекс.Карты, пробки", "url": maps})
    return {"reply": "\n".join(lines), "sources": sources, "maps": maps}


async def get_currency() -> dict[str, str]:
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        response = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        response.raise_for_status()
        data = response.json()
    valute = data.get("Valute") or {}
    def _fmt(code: str) -> str:
        value = valute.get(code, {}).get("Value")
        return f"{float(value):.2f}" if value is not None else "—"

    date = data.get("Date", "")[:10]
    text = f"Курс ЦБ на {date}: доллар {_fmt('USD')} ₽, евро {_fmt('EUR')} ₽, юань {_fmt('CNY')} ₽."
    return {"reply": text, "title": "Курс ЦБ", "url": "https://www.cbr.ru/"}


async def get_news() -> dict[str, object]:
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS, follow_redirects=True) as client:
        response = await client.get("https://lenta.ru/rss/news")
        response.raise_for_status()
        xml = response.text
    root = ElementTree.fromstring(xml)
    items = []
    for item in root.findall(".//item")[:6]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append({"title": title, "url": link})
    lines = ["Свежие заголовки:"] + [f"— {row['title']}" for row in items]
    return {"reply": "\n".join(lines), "sources": items}


async def get_public_ip() -> dict[str, str]:
    async with httpx.AsyncClient(timeout=8.0, headers=HEADERS) as client:
        response = await client.get("https://api.ipify.org", params={"format": "json"})
        response.raise_for_status()
        ip = str(response.json().get("ip") or "").strip()
    return {"reply": f"Ваш внешний IP: {ip or 'не удалось определить'}.", "title": "IP", "url": "https://api.ipify.org"}


async def wiki_summary(topic: str) -> dict[str, str]:
    slug = quote(topic.strip())
    url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{slug}"
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    extract = (data.get("extract") or "").strip()
    if data.get("type") == "disambiguation":
        extract = extract or f"Несколько значений для «{topic}». Уточните запрос."
    title = data.get("title") or topic
    page = data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://ru.wikipedia.org/wiki/{slug}"
    return {"reply": extract or f"Нет статьи про «{topic}».", "title": title, "url": page}


async def translate_text(text: str, target: str = "ru") -> dict[str, str]:
    params = {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text}
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        response = await client.get("https://translate.googleapis.com/translate_a/single", params=params)
        response.raise_for_status()
        data = response.json()
    parts = []
    for row in data[0] or []:
        if row and row[0]:
            parts.append(row[0])
    result = "".join(parts).strip()
    return {"reply": result or "Не удалось перевести.", "title": "Перевод", "url": "https://translate.google.com"}
