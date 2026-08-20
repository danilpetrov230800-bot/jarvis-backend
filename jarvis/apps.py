from __future__ import annotations

import os
from pathlib import Path

from jarvis.desktop import open_app, open_url
from jarvis.permissions import allowed, deny_message


def _menu_roots() -> list[Path]:
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    roots = []
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [path for path in roots if path.exists()]


def list_apps(limit: int = 80) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in _menu_roots():
        for path in root.rglob("*.lnk"):
            name = path.stem
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append({"name": name, "path": str(path)})
            if len(found) >= limit:
                return found
    return found


def launch_named(name: str) -> str:
    if not allowed("RUN_APPLICATIONS"):
        return deny_message("RUN_APPLICATIONS")
    needle = name.strip().lower()
    if not needle:
        return "Не поняла, какую программу открыть."
    for app in list_apps(limit=200):
        if needle in app["name"].lower():
            try:
                os.startfile(app["path"])  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                return f"Нашла {app['name']}. Запуск ярлыков доступен в Windows."
            return f"Открываю {app['name']}."
    launched = open_app(needle)
    if launched:
        return f"Запускаю {launched}."
    open_url("https://www.google.com/search?q=" + name)
    return f"Не нашла «{name}» в меню Пуск. Открыла поиск."
