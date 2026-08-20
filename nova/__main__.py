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

from nova.boot import prepare, write_crash
from nova.paths import app_root

prepare()

APP_ROOT = app_root()
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

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


def _serve(app, host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        lifespan="on",
        reload=False,
        workers=1,
    )
    uvicorn.Server(config).run()


def main() -> None:
    from nova.app import app, kernel
    from nova.logging_service import LogService

    log = LogService()
    parser = argparse.ArgumentParser(description="NOVA personal assistant")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    args, _ = parser.parse_known_args()

    settings = kernel.settings.current
    host = args.host or settings.host
    port = _find_port(host, args.port or settings.port)
    url = f"http://{host}:{port}"
    log.info("starting NOVA", url=url)

    no_window = args.no_window or os.environ.get("NOVA_NO_WINDOW") == "1" or not settings.open_window
    if no_window:
        _serve(app, host, port)
        return

    server = threading.Thread(target=lambda: _serve(app, host, port), daemon=True)
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
        raise SystemExit(main() or 0)
    except Exception as exc:
        write_crash(exc)
        logging.basicConfig(level=logging.ERROR)
        logging.exception("NOVA crashed")
        traceback.print_exc()
        sys.exit(1)
