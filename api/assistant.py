"""Маршрутизатор намерений Nova.

Определяет, нужен ли инструмент (погода, поиск, курс, время, маршрут,
новости, калькулятор) или управление ПК, и выполняет его. Работает
детерминированно — не зависит от способностей языковой модели, поэтому
инструменты срабатывают надёжно.
"""

from __future__ import annotations

import re
from typing import Optional

from . import system_control as sysctl
from . import tools

_FILLER = {"сейчас", "сегодня", "завтра", "пожалуйста", "плиз", "город", "погода"}


def _clean_place(raw: str) -> str:
    words = [w for w in re.split(r"[\s,]+", raw.strip()) if w and w.lower() not in _FILLER]
    return " ".join(words[:2])


def _place_after(text: str, preps: str) -> Optional[str]:
    m = re.search(rf"(?:{preps})\s+([A-Za-zА-Яа-яЁё\-]+(?:\s+[A-Za-zА-Яа-яЁё\-]+)?)", text)
    return _clean_place(m.group(1)) if m else None


def _num(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})", text)
    return int(m.group(1)) if m else None


def detect_and_run(text: str) -> dict:
    """Возвращает {events, context, direct, used}."""
    t = text.lower().strip()
    events: list[dict] = []

    def pack(result: dict) -> dict:
        events.append(result)
        return {
            "events": events,
            "context": "\n\n".join(e.get("summary", "") for e in events),
            "direct": "\n\n".join(e.get("summary", "") for e in events),
            "used": True,
        }

    # --- Управление ПК ---
    if re.search(r"\b(громкост|звук)\b", t) and ("выключ" in t or "mute" in t or "без звук" in t):
        return pack({**sysctl.mute(True), "tool": "system", "summary": sysctl.mute(True)["message"]})
    if re.search(r"громкост|звук на|volume", t):
        n = _num(t)
        if n is not None:
            r = sysctl.set_volume(n)
            return pack({"tool": "system", "title": "Громкость", "summary": r["message"], "data": r, "ok": r["ok"]})
    if re.search(r"яркост|brightness", t):
        n = _num(t)
        if n is not None:
            r = sysctl.set_brightness(n)
            return pack({"tool": "system", "title": "Яркость", "summary": r["message"], "data": r, "ok": r["ok"]})
    if re.search(r"пауз|play|играй|следующ.*трек|предыдущ.*трек|next track|переключи трек", t):
        action = "next" if "следующ" in t or "next" in t else "prev" if "предыдущ" in t else "play"
        r = sysctl.media(action)
        return pack({"tool": "system", "title": "Медиа", "summary": r["message"], "data": r, "ok": r["ok"]})
    if re.search(r"заблокир|блокировк.*экран|lock screen", t):
        r = sysctl.power("lock")
        return pack({"tool": "system", "title": "Питание", "summary": r["message"], "data": r, "ok": r["ok"]})
    if re.search(r"статус систем|загрузк.*(cpu|проц|памят)|сколько памят|системн.*статус|system status", t):
        r = sysctl.status()
        return pack({"tool": "system", "title": "Статус системы", "summary": r["message"], "data": r, "ok": r["ok"]})

    # --- Погода ---
    if re.search(r"погод|weather|температур|дожд|тепло ли|холодно ли|градус", t):
        place = _place_after(t, "в|во|in") or "Москва"
        return pack(tools.weather(place))

    # --- Курс валют ---
    if re.search(r"курс|обмен|доллар|евро|биткоин|рубл|фунт|юан|йен|тенге|гривн|₽|\$|€|£|exchange|convert|\b(usd|eur|rub|gbp|cny|jpy|kzt|uah|btc)\b", t):
        found = re.findall(r"[a-zа-яё]+|[$€₽£¥]", t)
        codes = []
        for f in found:
            code = tools.normalize_currency(f)
            if code and code not in codes:
                codes.append(code)
        amt_m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        amount = float(amt_m.group(1).replace(",", ".")) if amt_m else 1.0
        if len(codes) >= 2:
            return pack(tools.currency(amount, codes[0], codes[1]))
        if len(codes) == 1:
            base = codes[0]
            target = "RUB" if base != "RUB" else "USD"
            return pack(tools.currency(amount, base, target))

    # --- Время ---
    if re.search(r"который час|сколько времени|\bвремя\b|what time|time in", t):
        place = _place_after(t, "в|во|in")
        return pack(tools.time_in(place))

    # --- Маршрут / пробки ---
    if re.search(r"пробк|маршрут|как доехать|сколько ехать|как добраться|route|traffic", t):
        m = re.search(r"(?:от|из)\s+(.+?)\s+(?:до|в|к)\s+(.+)", t)
        if m:
            return pack(tools.route(_clean_place(m.group(1)), _clean_place(m.group(2))))
        return pack(tools._err("route", "Уточни: «пробки от <откуда> до <куда>»."))

    # --- Новости ---
    if re.search(r"\bновост|\bnews\b", t):
        topic = re.sub(r".*(новости|news)\s*(о|про|about)?\s*", "", t).strip()
        return pack(tools.news(topic))

    # --- Калькулятор ---
    if re.search(r"посчитай|вычисли|сколько будет|calculate", t) or re.fullmatch(r"[\d\s\.\,\+\-\*\/\(\)%×÷\^]+", t):
        expr = re.sub(r"(посчитай|вычисли|сколько будет|calculate)", "", t).strip()
        return pack(tools.calculate(expr or t))

    # --- Википедия / поиск ---
    if re.search(r"кто так|что так|расскажи (о|про)|википед|wiki", t):
        q = re.sub(r".*(кто так\w+|что так\w+|расскажи (о|про)|википеди\w*|wiki)\s*", "", t).strip()
        return pack(tools.wikipedia(q or text))
    if re.search(r"загугли|погугли|найди|найти|поиск|поищи|search|google|в интернете|в гугле", t):
        q = re.sub(r"(загугли|погугли|найди|найти|поищи|поиск|search|google|в интернете|в гугле|в сети)", "", t).strip()
        return pack(tools.web_search(q or text))

    return {"events": [], "context": "", "direct": "", "used": False}
