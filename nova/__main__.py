from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

os.environ.setdefault("PYTHONUTF8", "1")

from dotenv import load_dotenv

load_dotenv(APP_ROOT / ".env")


def _find_port(host: str, preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, preferred))
            return preferred
        except OSError:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])


def main() -> None:
    from nova.app import app, kernel
    from nova.logging_service import LogService

    log = LogService()
    parser = argparse.ArgumentParser(description="NOVA personal assistant")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    args = parser.parse_args()

    settings = kernel.settings.current
    host = args.host or settings.host
    port = _find_port(host, args.port or settings.port)
    url = f"http://{host}:{port}"
    log.info("starting NOVA", url=url)

    import uvicorn

    no_window = args.no_window or os.environ.get("NOVA_NO_WINDOW") == "1" or not settings.open_window
    if no_window:
        uvicorn.run(app, host=host, port=port, log_level="warning")
        return

    server = threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"),
        daemon=True,
    )
    server.start()
    health = url.rstrip("/") + "/health"
    for _ in range(80):
        try:
            urllib.request.urlopen(health, timeout=0.4)
            break
        except Exception:
            time.sleep(0.15)
    try:
        if args.browser:
            webbrowser.open(url)
            server.join()
            return
        from nova.window import open_window

        open_window(url)
    except Exception:
        log.error("native window failed, opening browser")
        webbrowser.open(url)
        server.join()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.basicConfig(level=logging.ERROR)
        logging.exception("NOVA crashed")
        traceback.print_exc()
        sys.exit(1)
