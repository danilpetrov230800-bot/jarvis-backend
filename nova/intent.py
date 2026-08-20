from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from nova.tools.calculator import safe_calc

SITES = {
    "youtube": "https://www.youtube.com",
    "ютуб": "https://www.youtube.com",
    "google": "https://www.google.com",
    "гугл": "https://www.google.com",
    "yandex": "https://ya.ru",
    "яндекс": "https://ya.ru",
    "github": "https://github.com",
    "vk": "https://vk.com",
    "вк": "https://vk.com",
    "telegram": "https://web.telegram.org",
    "телеграм": "https://web.telegram.org",
    "gmail": "https://mail.google.com",
    "почта": "https://mail.google.com",
    "steam": "https://store.steampowered.com",
}

OPEN_RE = re.compile(
    r"^(?:nova|нова)?[,.\s]*(?:открой|открыть|запусти|запустить|включи)\s+(.+)$",
    re.I,
)
CALC_RE = re.compile(r"^(?:посчитай|сколько будет|вычисли)\s+(.+)$", re.I)
NOTE_RE = re.compile(r"^(?:запиши|заметка|заметку)\s*[:\-]?\s*(.+)$", re.I)
REMEMBER_RE = re.compile(r"^(?:нова[, ]*)?(?:запомни(?: что)?|запомни,?\s*что)\s+(.+)$", re.I)
ALWAYS_RE = re.compile(r"^(?:нова[, ]*)?всегда\s+делай\s+(.+)$", re.I)
WHEN_RE = re.compile(r"когда я говорю\s+(.+?),\s*(?:выполняй|делай)\s+(.+)$", re.I)
TIMER_RE = re.compile(r"(?:таймер|напомни(?:ть)? через)\s+(\d+)\s*(сек|мин|час)", re.I)
CREATE_FILE_RE = re.compile(r"(?:создай|создать)\s+файл\s+(.+)$", re.I)
FIND_PDF_RE = re.compile(r"найди.*pdf", re.I)
HELP_RE = re.compile(r"^(помощь|help|что ты умеешь|команды)$", re.I)


class IntentRouter:
    async def route(self, text: str, kernel: Any) -> dict[str, Any] | None:
        raw = text.strip()
        lowered = raw.lower().strip(" .!?…")
        if not lowered:
            return None

        if HELP_RE.match(lowered):
            return self._ok(help_text(), ["help"])

        if lowered in {"привет", "здравствуй", "здравствуйте", "хай", "hello", "hi"}:
            name = kernel.settings.current.assistant_name
            return self._ok(f"Привет. Я {name}. Можно просто писать или сказать «Нова».", ["greet"])

        if lowered in {"который час", "время", "сколько времени"}:
            now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y, %H:%M:%S")
            return self._ok(f"Сейчас {now} (Москва).", ["datetime"])

        remember = REMEMBER_RE.match(raw)
        if remember:
            fact = remember.group(1).strip()
            kernel.memory.add(fact, kind="long_term", category="learned", title=fact[:48])
            return self._ok("Запомнила.", ["memory"])

        always = ALWAYS_RE.match(raw)
        if always:
            kernel.memory.add("Всегда: " + always.group(1), kind="preference", category="rules")
            return self._ok("Буду учитывать это правило.", ["memory"])

        when = WHEN_RE.search(raw)
        if when:
            skill = kernel.skills.create(
                {
                    "name": when.group(1).strip()[:48],
                    "trigger": when.group(1).strip(),
                    "actions": [{"type": "chat_command", "value": when.group(2).strip()}],
                    "description": "Создано голосом/текстом",
                }
            )
            return self._ok(f"Сохранила навык «{skill['name']}».", ["skill"], extra={"skill": skill})

        if lowered.startswith("научись делать"):
            last = kernel.memory.conversation(limit=4)
            last_user = next((m["content"] for m in reversed(last) if m["role"] == "user"), raw)
            skill = kernel.skills.create(
                {
                    "name": last_user[:48],
                    "trigger": last_user,
                    "actions": [{"type": "chat_command", "value": last_user}],
                }
            )
            return self._ok(f"Навык «{skill['name']}» сохранён.", ["skill"], extra={"skill": skill})

        calc = CALC_RE.match(raw)
        if calc:
            try:
                value = safe_calc(calc.group(1))
            except Exception:
                return self._ok("Могу считать только числа и + - * /.", ["calculator"])
            return self._ok(f"Получается {value}.", ["calculator"])

        note = NOTE_RE.match(raw)
        if note:
            await kernel.tools.run("save_note", {"text": note.group(1)})
            return self._ok("Записала в заметки.", ["notes"])

        created = CREATE_FILE_RE.search(raw)
        if created:
            path = created.group(1).strip().strip("«»\"")
            result = await kernel.tools.run("create_file", {"path": path, "content": ""})
            return result

        if FIND_PDF_RE.search(raw):
            return await kernel.tools.run("find_files", {"extension": "pdf", "query": "pdf"})

        if "фотограф" in lowered or "фото за" in lowered:
            month = "08" if "август" in lowered else ""
            return await kernel.tools.run("find_files", {"extension": "photo", "month": month, "query": ""})

        if "дубликат" in lowered:
            return await kernel.tools.run("find_duplicates", {})

        if "архив" in lowered and any(w in lowered for w in ("сделай", "создай", "собери")):
            return await kernel.tools.run("archive", {"paths": [str(__import__('pathlib').Path.home() / 'Downloads')]})

        if "найди файл с текстом" in lowered or "найди файл с текстом" in lowered:
            query = raw.split("текстом", 1)[-1].strip(" .")
            return await kernel.tools.run("search_content", {"query": query})

        if any(p in lowered for p in ("что происходит с компьютером", "почему компьютер тормозит", "почему тормозит")):
            return await kernel.tools.run("diagnose_slow", {})

        if "систем" in lowered or lowered in {"состояние пк", "статус компьютера"}:
            return await kernel.tools.run("system_info", {})

        if "скриншот" in lowered or "снимок экрана" in lowered:
            return await kernel.tools.run("screenshot", {})

        if "посмотри на экран" in lowered or "что на экране" in lowered:
            return await kernel.tools.run("ocr_screen", {})

        if lowered in {"выключи звук", "без звука", "mute", "мут"}:
            return await kernel.tools.run("volume_mute", {})
        if lowered in {"громче", "сделай громче", "прибавь звук"}:
            return await kernel.tools.run("volume_up", {})
        if lowered in {"тише", "сделай тише", "убавь звук"}:
            return await kernel.tools.run("volume_down", {})
        if lowered in {"ярче", "сделай ярче"}:
            return await kernel.tools.run("set_brightness", {"value": 80})
        if lowered in {"темнее", "сделай темнее"}:
            return await kernel.tools.run("set_brightness", {"value": 30})
        if lowered in {"пауза", "play", "плей"}:
            return await kernel.tools.run("media_play", {})
        if "заблок" in lowered:
            return await kernel.tools.run("lock_pc", {})
        if lowered in {"буфер", "буфер обмена", "что в буфере"}:
            return await kernel.tools.run("clipboard_get", {})

        timer = TIMER_RE.search(raw)
        if timer:
            amount = int(timer.group(1))
            unit = timer.group(2)
            seconds = amount * (60 if unit.startswith("мин") else 3600 if unit.startswith("час") else 1)
            kernel.tasks.create(f"Таймер {amount} {unit}", kind="reminder", delay_seconds=seconds, payload={"notify": True})
            return self._ok(f"Таймер на {amount} {unit} поставлен.", ["timer"])

        if "погод" in lowered:
            city = re.sub(r".*погод[аеуы]?\s*(?:в\s+)?", "", lowered).strip(" .") or "Москва"
            return await kernel.tools.run("get_weather", {"location": city})
        if "курс" in lowered or "доллар" in lowered:
            return await kernel.tools.run("get_currency", {})
        if lowered.startswith("вики ") or lowered.startswith("что такое "):
            topic = re.sub(r"^(вики|что такое)\s+", "", raw, flags=re.I)
            return await kernel.tools.run("wiki_summary", {"topic": topic})
        if lowered.startswith("погугли ") or lowered.startswith("загугли ") or lowered.startswith("найди информацию"):
            query = re.sub(r"^(погугли|загугли|найди информацию)\s+", "", raw, flags=re.I)
            return await kernel.tools.run("web_search", {"query": query})

        opened = OPEN_RE.match(raw)
        if opened:
            target = opened.group(1).strip().strip(" .")
            for site, url in SITES.items():
                if site in target.lower():
                    await kernel.tools.run("browse_url", {"url": url}) if False else None
                    from nova.tools.files import resolve_user_path  # noqa: F401
                    import webbrowser

                    webbrowser.open(url)
                    return self._ok(f"Открываю {site}.", ["open_url"], sources=[{"title": site, "url": url}])
            result = await kernel.tools.run("open_app", {"name": target})
            if result.get("ok"):
                return result
            if target.lower() in {"youtube"} or "youtube" in target.lower():
                import webbrowser

                url = "https://www.youtube.com/results?search_query=" + quote_plus(target)
                webbrowser.open(url)
                return self._ok(f"Ищу: {target}", ["youtube"])
            return result

        skill = kernel.skills.match(raw)
        if skill:
            replies = []
            for action in skill.get("actions") or []:
                if action.get("type") == "chat_command":
                    nested = await kernel.handle_chat(action.get("value") or "", source="skill", nested=True)
                    replies.append(nested.get("reply") or "")
                elif action.get("type") == "tool":
                    tool_result = await kernel.tools.run(action.get("name"), action.get("args") or {})
                    replies.append(tool_result.get("reply") or "")
                elif action.get("type") == "delay":
                    import asyncio

                    await asyncio.sleep(float(action.get("seconds") or 1))
            return self._ok("\n".join(filter(None, replies)) or f"Навык «{skill['name']}» выполнен.", ["skill"])

        if any(word in lowered for word in ("сравни варианты", "подготовь результат", "найди информацию", "план")):
            return None  # let agent handle
        return None

    def _ok(self, reply: str, tools: list[str], sources: list | None = None, extra: dict | None = None) -> dict[str, Any]:
        payload = {"ok": True, "reply": reply, "tools": tools, "sources": sources or [], "provider": "local", "model": "nova-local"}
        if extra:
            payload.update(extra)
        return payload


def help_text() -> str:
    return (
        "Я NOVA — персональный ассистент. Работаю и без API-ключа.\n"
        "Примеры:\n"
        "• открой YouTube / запусти калькулятор\n"
        "• найди все PDF / создай файл заметка.txt\n"
        "• запомни, что меня зовут Данила\n"
        "• когда я говорю режим работы, открой проводник\n"
        "• что происходит с компьютером\n"
        "• погода Москва / курс доллара\n"
        "• громче / тише / скриншот / таймер 5 мин"
    )
