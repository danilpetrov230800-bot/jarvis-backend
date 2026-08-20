"""Инструменты Nova: погода, поиск, Википедия, курсы валют, время,
маршруты/пробки, новости, калькулятор. Все источники — без API-ключей.

Каждый инструмент возвращает словарь:
    { ok, tool, title, summary, data, source }
`summary` — готовый человекочитаемый текст (используется в демо-режиме и
как контекст для языковой модели).
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (NovaAssistant)"
TIMEOUT = 10


def _get(url: str, headers: Optional[dict] = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _get_json(url: str, headers: Optional[dict] = None):
    return json.loads(_get(url, headers))


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _err(tool: str, msg: str) -> dict:
    return {"ok": False, "tool": tool, "title": tool, "summary": msg, "data": {}, "source": ""}


# --------------------------------------------------------------------------
# Геокодирование (Open-Meteo) — общий помощник
# --------------------------------------------------------------------------
_CITY_ALIASES = {
    "питер": "Санкт-Петербург", "питере": "Санкт-Петербург", "спб": "Санкт-Петербург",
    "мск": "Москва", "нью-йорк": "New York", "нью йорк": "New York",
}


def _geo_variants(name: str):
    base = name.strip()
    low = base.lower()
    seen = set()

    def emit(v):
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            return v
        return None

    order = []
    if low in _CITY_ALIASES:
        order.append(_CITY_ALIASES[low])
    order.append(base)
    if low.endswith("е") and len(low) > 4:      # предложный падеж: Лондоне→Лондон
        order.append(base[:-1])
        order.append(base[:-1] + "а")           # Москве→Москва
    if len(low) > 4:
        order.append(base[:-1])
        order.append(base[:-2])
    for v in order:
        got = emit(v)
        if got:
            yield got


def _geocode_once(name: str) -> Optional[dict]:
    q = urllib.parse.quote(name)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=ru&format=json"
    try:
        data = _get_json(url)
    except Exception:
        return None
    res = (data or {}).get("results") or []
    if not res:
        return None
    r = res[0]
    return {
        "name": r.get("name"),
        "country": r.get("country", ""),
        "lat": r.get("latitude"),
        "lon": r.get("longitude"),
        "timezone": r.get("timezone", "UTC"),
    }


def geocode(name: str) -> Optional[dict]:
    for variant in _geo_variants(name):
        loc = _geocode_once(variant)
        if loc:
            return loc
    return None


# --------------------------------------------------------------------------
# Погода
# --------------------------------------------------------------------------
_WMO = {
    0: "ясно", 1: "малооблачно", 2: "переменная облачность", 3: "пасмурно",
    45: "туман", 48: "изморозь", 51: "морось", 53: "морось", 55: "сильная морось",
    61: "небольшой дождь", 63: "дождь", 65: "сильный дождь",
    71: "небольшой снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа",
    80: "ливень", 81: "ливень", 82: "сильный ливень",
    85: "снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом", 99: "гроза с градом",
}


def weather(city: str) -> dict:
    loc = geocode(city)
    if not loc:
        return _err("weather", f"Не нашла город «{city}».")
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={loc['lat']}&longitude={loc['lon']}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
        f"&timezone=auto&forecast_days=3"
    )
    try:
        d = _get_json(url)
    except Exception as e:
        return _err("weather", f"Погодный сервис недоступен: {e}")
    cur = d.get("current", {})
    daily = d.get("daily", {})
    code = cur.get("weather_code")
    desc = _WMO.get(code, "")
    place = f"{loc['name']}, {loc['country']}".strip(", ")
    summary = (
        f"Погода в {place}: сейчас {cur.get('temperature_2m')}°C ({desc}), "
        f"ощущается как {cur.get('apparent_temperature')}°C, влажность "
        f"{cur.get('relative_humidity_2m')}%, ветер {cur.get('wind_speed_10m')} км/ч."
    )
    if daily.get("time"):
        parts = []
        for i, day in enumerate(daily["time"][:3]):
            parts.append(
                f"{day}: {daily['temperature_2m_min'][i]}…{daily['temperature_2m_max'][i]}°C, "
                f"{_WMO.get(daily['weather_code'][i], '')}, осадки {daily['precipitation_probability_max'][i]}%"
            )
        summary += " Прогноз: " + "; ".join(parts) + "."
    return {
        "ok": True, "tool": "weather", "title": f"Погода · {place}",
        "summary": summary, "data": {"current": cur, "daily": daily, "location": loc},
        "source": "open-meteo.com",
    }


# --------------------------------------------------------------------------
# Веб-поиск (DuckDuckGo)
# --------------------------------------------------------------------------
def web_search(query: str, limit: int = 5) -> dict:
    results = []
    abstract = ""
    try:
        ia = _get_json(
            "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
                {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            )
        )
        abstract = ia.get("AbstractText") or ia.get("Answer") or ""
    except Exception:
        pass
    try:
        h = _get("https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query}))
        links = re.findall(r'<a[^>]*class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S)
        snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', h, re.S)
        for i, (url, title) in enumerate(links[:limit]):
            results.append({
                "title": _strip_tags(title),
                "url": html.unescape(url),
                "snippet": _strip_tags(snippets[i]) if i < len(snippets) else "",
            })
    except Exception as e:
        if not abstract:
            return _err("web_search", f"Поиск недоступен: {e}")

    lines = []
    if abstract:
        lines.append(abstract)
    for r in results:
        lines.append(f"• {r['title']} — {r['snippet']} ({r['url']})")
    summary = f"Результаты по запросу «{query}»:\n" + "\n".join(lines) if lines else \
        f"По запросу «{query}» ничего не нашлось."
    return {
        "ok": True, "tool": "web_search", "title": f"Поиск · {query}",
        "summary": summary, "data": {"abstract": abstract, "results": results},
        "source": "duckduckgo.com",
    }


# --------------------------------------------------------------------------
# Википедия
# --------------------------------------------------------------------------
def wikipedia(query: str, lang: str = "ru") -> dict:
    try:
        s = _get_json(
            f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": query,
                "format": "json", "srlimit": 1,
            })
        )
        hits = s.get("query", {}).get("search", [])
        if not hits:
            return _err("wikipedia", f"В Википедии нет статьи по «{query}».")
        title = hits[0]["title"]
        summ = _get_json(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
        extract = summ.get("extract", "")
        page = summ.get("content_urls", {}).get("desktop", {}).get("page", "")
        return {
            "ok": True, "tool": "wikipedia", "title": f"Википедия · {title}",
            "summary": f"{title}. {extract}", "data": {"title": title, "extract": extract, "url": page},
            "source": "wikipedia.org",
        }
    except Exception as e:
        return _err("wikipedia", f"Википедия недоступна: {e}")


# --------------------------------------------------------------------------
# Курсы валют
# --------------------------------------------------------------------------
_CUR_ALIASES = {
    "доллар": "USD", "доллара": "USD", "долларов": "USD", "бакс": "USD", "usd": "USD", "$": "USD",
    "евро": "EUR", "eur": "EUR", "€": "EUR",
    "рубль": "RUB", "рубля": "RUB", "рублей": "RUB", "руб": "RUB", "rub": "RUB", "₽": "RUB",
    "фунт": "GBP", "gbp": "GBP", "юань": "CNY", "cny": "CNY", "йена": "JPY", "jpy": "JPY",
    "тенге": "KZT", "kzt": "KZT", "гривна": "UAH", "uah": "UAH", "биткоин": "BTC", "btc": "BTC",
}


_CUR_PREFIX = [
    ("доллар", "USD"), ("бакс", "USD"), ("евро", "EUR"), ("рубл", "RUB"), ("руб", "RUB"),
    ("фунт", "GBP"), ("юан", "CNY"), ("йен", "JPY"), ("иен", "JPY"), ("тенге", "KZT"),
    ("гривн", "UAH"), ("биткоин", "BTC"), ("bitcoin", "BTC"),
]
_CUR_SYMBOLS = {"$": "USD", "€": "EUR", "₽": "RUB", "£": "GBP", "¥": "JPY"}
_CUR_CODES = {"usd", "eur", "rub", "gbp", "cny", "jpy", "kzt", "uah", "btc"}


def normalize_currency(word: str) -> Optional[str]:
    w = word.lower().strip()
    if w in _CUR_SYMBOLS:
        return _CUR_SYMBOLS[w]
    if w in _CUR_CODES:
        return w.upper()
    for pre, code in _CUR_PREFIX:
        if w.startswith(pre):
            return code
    return None


def currency(amount: float, base: str, target: str) -> dict:
    base, target = base.upper(), target.upper()
    try:
        d = _get_json(f"https://open.er-api.com/v6/latest/{base}")
        rates = d.get("rates", {})
        if target not in rates:
            return _err("currency", f"Не знаю курс {base}→{target}.")
        rate = rates[target]
        value = round(amount * rate, 2)
        return {
            "ok": True, "tool": "currency", "title": f"Курс · {base}→{target}",
            "summary": f"{amount:g} {base} = {value:g} {target} (курс {rate:g}).",
            "data": {"amount": amount, "base": base, "target": target, "rate": rate, "result": value},
            "source": "exchangerate-api.com",
        }
    except Exception as e:
        return _err("currency", f"Сервис курсов недоступен: {e}")


# --------------------------------------------------------------------------
# Время
# --------------------------------------------------------------------------
def time_in(city: Optional[str] = None) -> dict:
    tzname = "UTC"
    place = "UTC"
    if city:
        loc = geocode(city)
        if loc:
            tzname = loc["timezone"]
            place = f"{loc['name']}, {loc['country']}".strip(", ")
    try:
        now = datetime.now(ZoneInfo(tzname))
    except Exception:
        now = datetime.utcnow()
        tzname = "UTC"
    stamp = now.strftime("%H:%M, %d.%m.%Y")
    return {
        "ok": True, "tool": "time", "title": f"Время · {place}",
        "summary": f"Сейчас в {place}: {stamp} ({tzname}).",
        "data": {"time": stamp, "timezone": tzname, "iso": now.isoformat()},
        "source": "zoneinfo",
    }


# --------------------------------------------------------------------------
# Маршрут / «пробки» (OSRM, время в пути по дорогам)
# --------------------------------------------------------------------------
def route(origin: str, destination: str) -> dict:
    a, b = geocode(origin), geocode(destination)
    if not a or not b:
        return _err("route", "Не смогла определить один из адресов.")
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{a['lon']},{a['lat']};{b['lon']},{b['lat']}?overview=false"
    )
    try:
        d = _get_json(url)
        rt = (d.get("routes") or [{}])[0]
        dur = rt.get("duration", 0) / 60.0
        dist = rt.get("distance", 0) / 1000.0
        return {
            "ok": True, "tool": "route", "title": f"Маршрут · {a['name']} → {b['name']}",
            "summary": (
                f"От {a['name']} до {b['name']}: ~{dist:.0f} км, время в пути на авто "
                f"~{dur:.0f} мин (по дорожному графу; реальные пробки зависят от времени суток)."
            ),
            "data": {"distance_km": round(dist, 1), "duration_min": round(dur), "from": a, "to": b},
            "source": "project-osrm.org",
        }
    except Exception as e:
        return _err("route", f"Маршрутный сервис недоступен: {e}")


# --------------------------------------------------------------------------
# Новости (Google News RSS)
# --------------------------------------------------------------------------
def news(topic: str = "", limit: int = 5) -> dict:
    if topic:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": topic, "hl": "ru", "gl": "RU", "ceid": "RU:ru"}
        )
    else:
        url = "https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru"
    try:
        xml = _get(url)
        items = re.findall(r"<item>(.*?)</item>", xml, re.S)[:limit]
        headlines = []
        for it in items:
            m = re.search(r"<title>(.*?)</title>", it, re.S)
            if m:
                headlines.append(_strip_tags(m.group(1)))
        if not headlines:
            return _err("news", "Не удалось получить новости.")
        title = f"Новости{' · ' + topic if topic else ''}"
        summary = title + ":\n" + "\n".join(f"• {h}" for h in headlines)
        return {
            "ok": True, "tool": "news", "title": title, "summary": summary,
            "data": {"headlines": headlines, "topic": topic}, "source": "news.google.com",
        }
    except Exception as e:
        return _err("news", f"Новостной сервис недоступен: {e}")


# --------------------------------------------------------------------------
# Калькулятор (безопасный)
# --------------------------------------------------------------------------
def calculate(expression: str) -> dict:
    expr = expression.replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", ".")
    if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s%]+", expr):
        return _err("calculate", "Могу считать только арифметику: + - * / ( ) %.")
    try:
        value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 — вход отфильтрован regex
        return {
            "ok": True, "tool": "calculate", "title": "Калькулятор",
            "summary": f"{expression} = {value}", "data": {"expression": expression, "result": value},
            "source": "local",
        }
    except Exception:
        return _err("calculate", "Не смогла вычислить выражение.")
