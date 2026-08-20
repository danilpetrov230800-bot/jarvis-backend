from __future__ import annotations

import shutil
import socket
import sqlite3
import sys
from typing import Any

from jarvis.config import DATA_DIR, ROOT, load_settings
from jarvis.permissions import list_permissions
from jarvis.storage import DATABASE, connect, initialize


def _result(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def run_diagnostics() -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    try:
        initialize()
        with connect() as db:
            db.execute("SELECT 1").fetchone()
        checks.append(_result("database", "PASS", f"SQLite {sqlite3.sqlite_version}; {DATABASE}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(_result("database", "FAIL", str(exc)))

    settings = load_settings()
    provider_ready = settings.provider == "ollama" or bool(settings.api_key)
    checks.append(_result("ai_provider", "PASS" if provider_ready else "WARNING", settings.provider if provider_ready else "Локальные команды доступны без AI API"))
    checks.append(_result("voice_tts", "PASS" if sys.platform == "win32" else "WARNING", "Windows SAPI + Edge TTS" if sys.platform == "win32" else "Проверка устройства доступна в Windows"))
    checks.append(_result("voice_stt", "PASS" if sys.platform == "win32" else "WARNING", "WebView2 Speech Recognition" if sys.platform == "win32" else "Проверка микрофона доступна в Windows"))
    checks.append(_result("storage", "PASS" if DATA_DIR.exists() and DATA_DIR.is_dir() else "WARNING", str(DATA_DIR)))
    checks.append(_result("assets", "PASS" if (ROOT / "static" / "index.html").is_file() else "FAIL", str(ROOT / "static")))
    free = shutil.disk_usage(DATA_DIR).free if DATA_DIR.exists() else shutil.disk_usage(DATA_DIR.parent).free
    checks.append(_result("disk", "PASS" if free > 500 * 1024**2 else "WARNING", f"{free / 1024**3:.1f} GB свободно"))
    checks.append(_result("permissions", "PASS", f"{sum(bool(p['enabled']) for p in list_permissions())} разрешений включено"))
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            online = True
    except OSError:
        online = False
    checks.append(_result("network", "PASS" if online else "WARNING", "Online" if online else "Offline mode"))
    overall = "FAIL" if any(item["status"] == "FAIL" for item in checks) else ("WARNING" if any(item["status"] == "WARNING" for item in checks) else "PASS")
    return {"status": overall, "checks": checks}
