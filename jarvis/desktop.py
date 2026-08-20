from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus
from zoneinfo import ZoneInfo

from jarvis.config import DATA_DIR, ROOT

NOTES_PATH = DATA_DIR / "notes.txt"

SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "ютуб": "https://www.youtube.com",
    "youtu": "https://www.youtube.com",
    "google": "https://www.google.com",
    "гугл": "https://www.google.com",
    "yandex": "https://ya.ru",
    "яндекс": "https://ya.ru",
    "github": "https://github.com",
    "гитхаб": "https://github.com",
    "vk": "https://vk.com",
    "вк": "https://vk.com",
    "вконтакте": "https://vk.com",
    "telegram": "https://web.telegram.org",
    "телеграм": "https://web.telegram.org",
    "gmail": "https://mail.google.com",
    "почта": "https://mail.google.com",
    "twitch": "https://www.twitch.tv",
    "твич": "https://www.twitch.tv",
    "discord": "https://discord.com/app",
    "дискорд": "https://discord.com/app",
    "steam": "https://store.steampowered.com",
    "стим": "https://store.steampowered.com",
    "netflix": "https://www.netflix.com",
    "нетфликс": "https://www.netflix.com",
    "wikipedia": "https://ru.wikipedia.org",
    "вики": "https://ru.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "translate": "https://translate.google.com/?sl=en&tl=ru",
    "переводчик": "https://translate.google.com/?sl=en&tl=ru",
}

APPS: dict[str, list[str]] = {
    "блокнот": ["notepad.exe"],
    "notepad": ["notepad.exe"],
    "калькулятор": ["calc.exe"],
    "calc": ["calc.exe"],
    "проводник": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "паинт": ["mspaint.exe"],
    "командная строка": ["cmd.exe"],
    "терминал": ["powershell.exe"],
    "powershell": ["powershell.exe"],
    "диспетчер задач": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "настройки": ["ms-settings:"],
    "chrome": ["chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "хром": ["chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "edge": ["msedge.exe"],
    "браузер": ["msedge.exe", "chrome.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "spotify": ["spotify.exe"],
    "спотифай": ["spotify.exe"],
    "steam": ["steam.exe"],
    "стим": ["steam.exe"],
}

OPEN_RE = re.compile(
    r"^(?:nova|нова|пожалуйста|плиз)?[,.\s]*(?:открой|открыть|запусти|запустить|включи|показать|покажи)\s+(.+)$",
    re.I,
)
SEARCH_OPEN_RE = re.compile(
    r"^(?:найди|найти|погугли|поиск)\s+(?:на\s+)?(?:ютуб[еа]?|youtube)\s+(.+)$",
    re.I,
)
NOTE_RE = re.compile(r"^(?:запиши|заметка|заметку|note)\s*[:\-]?\s*(.+)$", re.I)
COPY_RE = re.compile(r"^(?:скопируй|копируй|copy)\s*[:\-]?\s*(.+)$", re.I)
CALC_RE = re.compile(r"^(?:посчитай|сколько будет|вычисли)\s+(.+)$", re.I)
TIMER_RE = re.compile(r"^(?:таймер|напомни(?:ть)? через)\s+(\d+)\s*(сек(?:унд(?:ы|у)?)?|мин(?:ут(?:ы|у)?)?|час(?:а|ов)?)", re.I)
URL_RE = re.compile(r"https?://[^\s]+", re.I)
DOMAIN_RE = re.compile(r"\b([a-z0-9-]+\.(?:com|ru|net|org|io|tv|dev|gg))\b", re.I)


@dataclass
class ActionResult:
    reply: str
    tools: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)


def _win() -> bool:
    return sys.platform == "win32"


def open_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    if _win():
        subprocess.Popen(["cmd", "/c", "start", "", url], close_fds=True)
    else:
        webbrowser.open(url)
    return url


def open_app(name: str) -> str | None:
    key = name.strip().lower()
    candidates = APPS.get(key, [name])
    for item in candidates:
        if item.endswith(":") or item.startswith("ms-"):
            if _win():
                os.startfile(item)  # type: ignore[attr-defined]
                return item
            continue
        resolved = shutil.which(item) or (item if Path(item).exists() else None)
        if not resolved:
            continue
        if _win():
            subprocess.Popen(["cmd", "/c", "start", "", resolved], close_fds=True)
        else:
            subprocess.Popen([resolved])
        return resolved
    return None


def take_screenshot() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    if _win():
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
            "$img = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($img); "
            "$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $img.Size); "
            f"$img.Save('{path.as_posix()}')"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False)
    if not path.exists():
        path.write_bytes(b"")
    return path


def system_info() -> str:
    cpu = platform.processor() or platform.machine()
    target = ROOT.anchor or str(ROOT)
    try:
        usage = shutil.disk_usage(target)
        disk = f"{usage.free / 1024**3:.1f} ГБ свободно"
    except Exception:
        disk = "неизвестно"
    lines = [
        f"Система: {platform.system()} {platform.release()}",
        f"Компьютер: {platform.node()}",
        f"Процессор: {cpu}",
        f"Python: {platform.python_version()}",
        f"Диск: {disk}",
        f"Папка NOVA: {ROOT}",
    ]
    battery = _battery_line()
    if battery:
        lines.append(battery)
    return "\n".join(lines)


def _battery_line() -> str:
    if not _win():
        return ""
    script = "Get-CimInstance Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return ""
    value = (result.stdout or "").strip().splitlines()
    if value and value[-1].isdigit():
        return f"Заряд батареи: {value[-1]}%"
    return ""


def save_note(text: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with NOTES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {text.strip()}\n")
    return NOTES_PATH


def read_notes() -> str:
    if not NOTES_PATH.exists():
        return "Заметок пока нет."
    return NOTES_PATH.read_text(encoding="utf-8").strip() or "Заметок пока нет."


def now_moscow() -> str:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now.strftime("%d.%m.%Y, %H:%M:%S (Москва)")


def safe_eval_math(expr: str) -> str:
    allowed = expr.strip().replace(",", ".")
    if not re.fullmatch(r"[0-9.\s+\-*/()]+", allowed):
        raise ValueError("можно только цифры и + - * /")
    return str(eval(allowed, {"__builtins__": {}}, {}))  # noqa: S307 — filtered charset


def lock_workstation() -> str:
    if _win():
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Блокирую компьютер."
    return "Блокировка доступна только в Windows."


def get_clipboard() -> str:
    if _win():
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        text = (result.stdout or "").strip()
        return text or "Буфер обмена пуст."
    return "Буфер обмена читаю только в Windows."


def set_clipboard(text: str) -> str:
    if _win():
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            timeout=8,
            check=False,
        )
        return "Скопировала в буфер обмена."
    return "Копирование в буфер доступно в Windows."


def _notify_timer(label: str) -> None:
    if _win():
        script = (
            "$w = New-Object -ComObject WScript.Shell; "
            "$w.Popup('NOVA: timer', 8, 'NOVA', 64)"
        )
        subprocess.Popen(["powershell", "-NoProfile", "-Command", script])
        return
    print(f"NOVA timer: {label}", flush=True)


def handle_intent(text: str) -> ActionResult | None:
    raw = text.strip()
    lowered = raw.lower().strip(" .!?")
    if not lowered:
        return None

    if lowered in {"помощь", "help", "что ты умеешь", "команды"}:
        return ActionResult(reply=help_text(), tools=["help"])

    if "который час" in lowered or lowered in {"время", "сколько времени"}:
        return ActionResult(reply=f"Сейчас {now_moscow()}.", tools=["datetime"])

    if lowered in {"дата", "какой сегодня день"}:
        return ActionResult(reply=f"Сегодня {now_moscow()}.", tools=["datetime"])

    if "систем" in lowered and ("инф" in lowered or "статус" in lowered or "компьютер" in lowered):
        return ActionResult(reply=system_info(), tools=["system_info"])

    if "скриншот" in lowered or "снимок экрана" in lowered:
        path = take_screenshot()
        return ActionResult(reply=f"Снимок экрана сохранён: {path}", tools=["screenshot"])

    if lowered in {"покажи заметки", "заметки", "моих заметок"}:
        return ActionResult(reply=read_notes(), tools=["notes"])

    note = NOTE_RE.match(raw)
    if note:
        save_note(note.group(1))
        return ActionResult(reply="Записала в заметки.", tools=["notes"])

    if "заблок" in lowered or lowered in {"lock", "заблокируй", "заблокировать"}:
        return ActionResult(reply=lock_workstation(), tools=["lock"])

    if lowered in {"буфер", "буфер обмена", "что в буфере", "clipboard"}:
        return ActionResult(reply=get_clipboard(), tools=["clipboard"])

    copied = COPY_RE.match(raw)
    if copied:
        return ActionResult(reply=set_clipboard(copied.group(1).strip()), tools=["clipboard"])

    from jarvis.pc_control import handle_pc_intent

    pc = handle_pc_intent(lowered)
    if pc:
        return ActionResult(reply=pc.reply, tools=pc.tools)

    calc = CALC_RE.match(raw)
    if calc:
        try:
            value = safe_eval_math(calc.group(1))
        except Exception as exc:  # noqa: BLE001
            return ActionResult(reply=f"Не смогла посчитать: {exc}", tools=["calc"])
        return ActionResult(reply=f"Получается {value}.", tools=["calc"])

    yt = SEARCH_OPEN_RE.match(raw)
    if yt:
        url = "https://www.youtube.com/results?search_query=" + quote_plus(yt.group(1))
        open_url(url)
        return ActionResult(reply=f"Ищу на YouTube: {yt.group(1)}.", tools=["youtube"], sources=[{"title": "YouTube", "url": url}])

    timer = TIMER_RE.match(raw)
    if timer:
        amount = int(timer.group(1))
        unit = timer.group(2).lower()
        seconds = amount
        if unit.startswith("мин"):
            seconds = amount * 60
        elif unit.startswith("час"):
            seconds = amount * 3600
        threading.Timer(seconds, lambda: _notify_timer(f"{amount} {timer.group(2)}")).start()
        return ActionResult(reply=f"Таймер на {amount} {timer.group(2)} поставлен. Напомню, пока Nova запущена.", tools=["timer"])

    opened = _try_open(raw, lowered)
    if opened:
        return opened
    return None


def _try_open(raw: str, lowered: str) -> ActionResult | None:
    url_match = URL_RE.search(raw)
    if url_match and any(word in lowered for word in ("открой", "открыть", "запусти", "зайди")):
        url = open_url(url_match.group(0))
        return ActionResult(reply=f"Открываю {url}", tools=["open_url"], sources=[{"title": url, "url": url}])

    match = OPEN_RE.match(raw)
    target = match.group(1).strip().strip(" .") if match else ""
    if not target:
        for site_name, site_url in SITES.items():
            if re.search(rf"\b{re.escape(site_name)}\b", lowered):
                if any(w in lowered for w in ("открой", "открыть", "запусти", "зайди")):
                    open_url(site_url)
                    return ActionResult(reply=f"Открываю {site_name}.", tools=["open_url"], sources=[{"title": site_name, "url": site_url}])
        return None

    target_l = target.lower()
    for site_name, site_url in SITES.items():
        if site_name in target_l or target_l in site_name:
            open_url(site_url)
            return ActionResult(reply=f"Открываю {site_name}.", tools=["open_url"], sources=[{"title": site_name, "url": site_url}])

    domain = DOMAIN_RE.search(target)
    if domain:
        url = open_url(domain.group(1))
        return ActionResult(reply=f"Открываю {url}", tools=["open_url"], sources=[{"title": url, "url": url}])

    app = open_app(target_l)
    if app:
        return ActionResult(reply=f"Запускаю {target}.", tools=["open_app"])

    downloads = Path.home() / "Downloads"
    if "загруз" in target_l and downloads.exists():
        if _win():
            os.startfile(downloads)  # type: ignore[attr-defined]
        else:
            webbrowser.open(downloads.as_uri())
        return ActionResult(reply="Открываю папку загрузок.", tools=["open_folder"])

    return ActionResult(
        reply=f"Не нашла приложение «{target}». Могу открыть сайт, блокнот, калькулятор, проводник, Chrome, YouTube.",
        tools=["open_unknown"],
    )


def help_text() -> str:
    return (
        "Я Nova — могу работать без API-ключа.\n"
        "Примеры:\n"
        "• открой YouTube / GitHub / VK / почту\n"
        "• запусти блокнот / калькулятор / проводник / Chrome\n"
        "• найди на ютубе lo-fi\n"
        "• который час / погода Москва / пробки Москва / курс доллара / новости\n"
        "• громче / тише / выключи звук / ярче / темнее / пауза\n"
        "• переведи hello / вики квантовый компьютер / погугли python / мой ip\n"
        "• таймер 5 минут / скопируй: текст / буфер обмена / заблокируй\n"
        "• сделай скриншот / запиши: купить молоко / посчитай 24*7\n"
        "• открой wikipedia.org\n"
        "А если спросите «что такое кванты» — поищу в интернете."
    )
