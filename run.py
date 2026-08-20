#!/usr/bin/env python3
"""Однокликовый запуск Nova для обычного пользователя.

Скрипт сам:
  1) ставит Python-зависимости,
  2) устанавливает локальный ИИ (Ollama), если его нет,
  3) запускает локальный ИИ и в фоне скачивает модель,
  4) поднимает веб-сервер Nova и открывает браузер.

Ничего настраивать не нужно. Если локальный ИИ ещё не готов — Nova работает
в демо-режиме и автоматически переключится на ИИ, как только модель скачается.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

HOST = os.environ.get("NOVA_HOST", "127.0.0.1")
PORT = int(os.environ.get("NOVA_PORT", "8000"))
MODEL = os.environ.get("NOVA_LOCAL_MODEL", "qwen2.5:3b")
OSNAME = platform.system()
OLLAMA_API = "http://127.0.0.1:11434"


def log(msg: str) -> None:
    print(f"[Nova] {msg}", flush=True)


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


# --------------------------------------------------------------------------
def install_deps() -> None:
    log("Проверяю и ставлю зависимости…")
    reqs = os.path.join(ROOT, "requirements.txt")
    attempts = [
        [sys.executable, "-m", "pip", "install", "-q", "-r", reqs],
        [sys.executable, "-m", "pip", "install", "-q", "--user", "-r", reqs],
        [sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "-r", reqs],
    ]
    for args in attempts:
        try:
            if subprocess.run(args).returncode == 0:
                return
        except Exception:
            continue
    log("Не смог поставить зависимости автоматически — установи вручную: pip install -r requirements.txt")


def ensure_ollama() -> bool:
    if shutil.which("ollama"):
        return True
    log("Устанавливаю локальный ИИ (Ollama)…")
    try:
        if OSNAME == "Linux":
            subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
        elif OSNAME == "Darwin":
            if shutil.which("brew"):
                subprocess.run(["brew", "install", "ollama"])
            else:
                log("Открываю страницу загрузки Ollama — установи и перезапусти Nova.")
                webbrowser.open("https://ollama.com/download")
        elif OSNAME == "Windows":
            if shutil.which("winget"):
                subprocess.run([
                    "winget", "install", "-e", "--id", "Ollama.Ollama", "--silent",
                    "--accept-package-agreements", "--accept-source-agreements",
                ])
            else:
                log("Открываю страницу загрузки Ollama — установи и перезапусти Nova.")
                webbrowser.open("https://ollama.com/download")
    except Exception as e:  # noqa: BLE001
        log(f"Авто-установка Ollama не удалась: {e}")
    return shutil.which("ollama") is not None


def start_ollama() -> bool:
    if _http_ok(f"{OLLAMA_API}/api/version"):
        return True
    if not shutil.which("ollama"):
        return False
    log("Запускаю локальный ИИ…")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    for _ in range(30):
        if _http_ok(f"{OLLAMA_API}/api/version"):
            return True
        time.sleep(1)
    return False


def pull_model_background() -> None:
    def worker() -> None:
        if not shutil.which("ollama"):
            return
        try:
            with urllib.request.urlopen(f"{OLLAMA_API}/api/tags", timeout=3) as r:
                names = [m.get("name", "") for m in json.load(r).get("models", [])]
            if any(n.split(":")[0] == MODEL.split(":")[0] for n in names):
                log("Локальная модель на месте — Nova использует локальный ИИ.")
                return
        except Exception:
            pass
        log(f"Скачиваю модель {MODEL} (один раз, ~2 ГБ; может занять несколько минут)…")
        subprocess.run(["ollama", "pull", MODEL])
        log("Готово — Nova переключилась на локальный ИИ.")

    threading.Thread(target=worker, daemon=True).start()


def open_browser_when_ready() -> None:
    def worker() -> None:
        for _ in range(60):
            if _http_ok(f"http://{HOST}:{PORT}/api/health"):
                webbrowser.open(f"http://{HOST}:{PORT}")
                return
            time.sleep(0.5)

    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    print("=" * 56)
    print("   NOVA — персональный ИИ-ассистент")
    print("=" * 56)

    install_deps()

    if ensure_ollama():
        if start_ollama():
            pull_model_background()
        else:
            log("Локальный ИИ не запустился — работаю в демо-режиме.")
    else:
        log("Ollama пока недоступна — запускаю в демо-режиме (подключится позже).")

    log(f"Открываю Nova: http://{HOST}:{PORT}  (для выхода — Ctrl+C)")
    open_browser_when_ready()

    import uvicorn
    from api.index import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Остановлено. До связи!")
