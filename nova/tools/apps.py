from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from nova.tools.base import ToolResult

KNOWN_APPS: dict[str, list[str]] = {
    "блокнот": ["notepad.exe"],
    "notepad": ["notepad.exe"],
    "калькулятор": ["calc.exe"],
    "calc": ["calc.exe"],
    "проводник": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "chrome": ["chrome.exe"],
    "хром": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "браузер": ["msedge.exe", "chrome.exe", "firefox.exe"],
    "firefox": ["firefox.exe"],
    "steam": ["steam.exe"],
    "стим": ["steam.exe"],
    "telegram": ["telegram.exe"],
    "телеграм": ["telegram.exe"],
    "discord": ["discord.exe"],
    "spotify": ["spotify.exe"],
    "code": ["code.exe"],
    "vscode": ["code.exe"],
    "photoshop": ["photoshop.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powershell": ["powershell.exe"],
    "терминал": ["wt.exe", "powershell.exe"],
    "диспетчер задач": ["taskmgr.exe"],
}


def _win() -> bool:
    return sys.platform == "win32"


def index_start_menu() -> dict[str, str]:
    found: dict[str, str] = {}
    if not _win():
        return found
    roots = []
    program_data = os.environ.get("PROGRAMDATA")
    appdata = os.environ.get("APPDATA")
    if program_data:
        roots.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    for root in roots:
        if not root.exists():
            continue
        for link in root.rglob("*.lnk"):
            found[link.stem.lower()] = str(link)
    return found


def _registry_apps() -> dict[str, str]:
    found: dict[str, str] = {}
    if not _win():
        return found
    try:
        import winreg
    except Exception:
        return found
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        sub = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, sub) as item:
                            name = str(winreg.QueryValueEx(item, "DisplayName")[0])
                            location = ""
                            try:
                                location = str(winreg.QueryValueEx(item, "DisplayIcon")[0]).split(",")[0].strip('"')
                            except OSError:
                                try:
                                    location = str(winreg.QueryValueEx(item, "InstallLocation")[0])
                                except OSError:
                                    location = ""
                            if name:
                                found[name.lower()] = location
                    except OSError:
                        continue
        except OSError:
            continue
    return found


_CACHE: dict[str, str] | None = None


def app_index() -> dict[str, str]:
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        _CACHE.update(_registry_apps())
        _CACHE.update(index_start_menu())
    return _CACHE


def refresh_index() -> dict[str, str]:
    global _CACHE
    _CACHE = None
    return app_index()


def resolve_app(name: str) -> str | None:
    key = name.strip().lower()
    for alias, candidates in KNOWN_APPS.items():
        if alias == key or alias in key:
            for item in candidates:
                found = shutil.which(item)
                if found:
                    return found
                if Path(item).exists():
                    return item
    index = app_index()
    if key in index:
        return index[key]
    for title, path in index.items():
        if key in title or title in key:
            return path
    which = shutil.which(name)
    return which


async def open_app(name: str = "", **_: Any) -> ToolResult:
    if not name:
        return ToolResult(False, "Назовите программу.")
    target = resolve_app(name)
    if not target:
        return ToolResult(False, f"Не нашла приложение «{name}».")
    try:
        if _win():
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([target])
    except Exception:
        return ToolResult(False, f"Не удалось запустить «{name}».")
    return ToolResult(True, f"Запускаю {name}.", {"path": target})


async def close_app(name: str = "", **_: Any) -> ToolResult:
    if not _win():
        return ToolResult(False, "Закрытие приложений доступно в Windows.")
    exe = (resolve_app(name) or name).split("\\")[-1]
    if not exe.lower().endswith(".exe"):
        exe += ".exe"
    result = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, text=True)
    if result.returncode != 0:
        return ToolResult(False, f"Не удалось закрыть {name}.")
    return ToolResult(True, f"Закрыла {name}.")


async def list_apps(**_: Any) -> ToolResult:
    names = sorted(set(list(KNOWN_APPS) + list(app_index())[:80]))
    return ToolResult(True, "Известные приложения: " + ", ".join(names[:40]), {"apps": names[:120]})
