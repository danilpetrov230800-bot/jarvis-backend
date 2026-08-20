from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from jarvis.net import find_free_port

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def main() -> None:
    from jarvis.config import load_settings
    from jarvis.app import app

    parser = argparse.ArgumentParser(description="NOVA — персональный ИИ-помощник")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    host = args.host or settings.host
    requested = args.port or settings.port
    port = find_free_port(host, requested)
    url = f"http://{host}:{port}"
    print(f"NOVA: {url}", flush=True)
    if settings.open_browser and not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            print(f"Не удалось открыть браузер: {exc}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
