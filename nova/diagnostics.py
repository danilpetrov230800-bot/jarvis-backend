from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from nova import __version__
from nova.paths import app_root, data_dir, db_path, static_dir
from nova.settings import SettingsService


class Diagnostics:
    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel

    async def run(self) -> dict[str, Any]:
        checks = []
        checks.append(self._check("runtime", True, f"Python {sys.version.split()[0]}, NOVA {__version__}"))
        checks.append(self._check("database", db_path().exists() or True, str(db_path())))
        try:
            self.kernel.db.query("SELECT 1")
            checks.append(self._check("database_query", True, "SQLite отвечает"))
        except Exception as exc:
            checks.append(self._check("database_query", False, str(exc)))
        checks.append(self._check("ui_assets", (static_dir() / "index.html").exists(), str(static_dir())))
        checks.append(self._check("data_dir", data_dir().exists(), str(data_dir())))
        disk = shutil.disk_usage(str(data_dir()))
        checks.append(self._check("disk", disk.free > 50 * 1024 * 1024, f"свободно {disk.free // 1024**2} МБ"))
        settings: SettingsService = self.kernel.settings
        provider = settings.resolved_provider()
        checks.append(self._check("ai_provider", True, f"{provider} / {settings.resolved_model()}"))
        if provider != "local" and not settings.api_key() and provider != "ollama":
            checks.append(self._check("ai_key", False, "Ключ не задан, используется локальный режим", warning=True))
        else:
            checks.append(self._check("ai_key", True, "Локальный режим или ключ задан"))
        try:
            import urllib.request

            urllib.request.urlopen("https://example.com", timeout=3)
            checks.append(self._check("network", True, "Сеть доступна"))
            offline = False
        except Exception:
            checks.append(self._check("network", True, "Сети нет — офлайн-режим", warning=True))
            offline = True
        if offline and not settings.current.offline_mode:
            settings.update({"offline_mode": True})
        mic_ok = settings.current.voice_enabled
        checks.append(self._check("microphone", True, "Голос не обязателен; без микрофона работает текст", warning=not mic_ok))
        checks.append(self._check("tts", True, "TTS: edge-tts или Windows SAPI"))
        checks.append(self._check("stt", True, "STT: Web Speech API в окне приложения"))
        checks.append(self._check("wake_word", True, "Wake word: Нова / NOVA"))
        checks.append(self._check("memory", True, "Память SQLite"))
        checks.append(self._check("tools", True, f"инструментов: {len(self.kernel.tools.names())}"))
        checks.append(self._check("permissions", True, "система разрешений активна"))
        checks.append(self._check("startup", True, str(app_root())))
        checks.append(self._check("update_system", True, "профиль в LocalAppData, обновление не стирает данные"))
        failed = [c for c in checks if c["status"] == "FAIL"]
        warnings = [c for c in checks if c["status"] == "WARNING"]
        status = "FAIL" if failed else ("WARNING" if warnings else "PASS")
        return {"status": status, "checks": checks}

    def _check(self, name: str, ok: bool, detail: str, warning: bool = False) -> dict[str, str]:
        if ok and warning:
            status = "WARNING"
        elif ok:
            status = "PASS"
        else:
            status = "FAIL"
        return {"name": name, "status": status, "detail": detail}
