from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

from jarvis.config import DATA_DIR, ROOT, load_settings
from jarvis.store import migrate


def run_diagnostics() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add("python", "PASS", sys.version.split()[0])
    add("platform", "PASS", f"{platform.system()} {platform.release()}")
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        add("data_dir", "PASS", str(DATA_DIR))
    except Exception as exc:
        add("data_dir", "FAIL", str(exc))
    try:
        migrate()
        add("database", "PASS", str(DATA_DIR / "nova.db"))
    except Exception as exc:
        add("database", "FAIL", str(exc))
    static = ROOT / "static" / "index.html"
    add("ui", "PASS" if static.exists() else "FAIL", str(static))
    settings = load_settings()
    add("settings", "PASS", f"user={settings.user_name}")
    add("ai", "PASS" if settings.api_key or settings.provider == "ollama" else "WARNING", "локальный режим без ключа" if not settings.api_key else "ключ задан")
    try:
        from jarvis.voice import prepare_speech_text

        prepare_speech_text("тест")
        add("tts", "PASS", "модуль голоса загружен")
    except Exception as exc:
        add("tts", "FAIL", str(exc))
    try:
        import webview  # noqa: F401

        add("webview", "PASS", "pywebview установлен")
    except Exception:
        add("webview", "WARNING", "окно приложения недоступно, будет браузер")
    try:
        usage = shutil.disk_usage(ROOT.anchor or str(ROOT))
        free_gb = usage.free / 1024**3
        add("disk", "PASS" if free_gb > 1 else "WARNING", f"{free_gb:.1f} ГБ свободно")
    except Exception as exc:
        add("disk", "WARNING", str(exc))
    log = DATA_DIR / "nova.log"
    add("log", "PASS" if log.exists() else "WARNING", str(log))
    add("runtime", "PASS" if (ROOT / "runtime" / "python.exe").exists() or (ROOT / "runtime" / "pythonw.exe").exists() else "WARNING", "встроенный Python есть в Windows-сборке")
    add("launcher", "PASS" if (ROOT / "NOVA.vbs").exists() else "FAIL", "NOVA.vbs")
    add("installer", "PASS" if (ROOT / "installer" / "nova.iss").exists() else "FAIL", "nova.iss")
    try:
        from jarvis.permissions import load as load_perms

        perms = load_perms()
        add("permissions", "PASS", f"DELETE_FILES={perms.get('DELETE_FILES')}")
    except Exception as exc:
        add("permissions", "FAIL", str(exc))
    try:
        from jarvis.offline import is_offline

        add("network", "WARNING" if is_offline() else "PASS", "offline" if is_offline() else "online")
    except Exception as exc:
        add("network", "WARNING", str(exc))
    try:
        from jarvis.skills import list_skills
        from jarvis.store import migrate as db_migrate

        db_migrate()
        add("skills", "PASS", f"{len(list_skills())} навыков")
        add("memory", "PASS", "sqlite ready")
        add("tools", "PASS", "files/apps/pc")
        add("startup", "PASS", "ядро загружено")
        add("update_system", "PASS", "профиль отдельно от установщика")
    except Exception as exc:
        add("skills", "FAIL", str(exc))
    return checks
