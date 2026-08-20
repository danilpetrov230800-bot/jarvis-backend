from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def main() -> None:
    from jarvis.config import load_settings
    from jarvis.app import app

    parser = argparse.ArgumentParser(description="JARVIS — персональный ИИ-помощник")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    url = f"http://{host}:{port}"
    if settings.open_browser and not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
