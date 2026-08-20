from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from dotenv import load_dotenv

from jarvis.config import DATA_DIR
from jarvis.net import find_free_port

load_dotenv(ROOT / ".env")
LOG = DATA_DIR / "nova.log"


def _setup_logging() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _open_when_ready(url: str) -> None:
    health = url.rstrip("/") + "/health"
    for _ in range(80):
        try:
            urllib.request.urlopen(health, timeout=0.5)
            break
        except Exception:
            time.sleep(0.15)
    logging.info("Opening UI %s", url)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", url], close_fds=True)
        else:
            webbrowser.open(url)
    except Exception:
        logging.exception("Failed to open browser")
        print(f"Open this URL in Chrome or Edge: {url}", flush=True)


def main() -> None:
    _setup_logging()
    from jarvis.config import load_settings
    from jarvis.app import app

    parser = argparse.ArgumentParser(description="NOVA personal assistant")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--browser", action="store_true", help="Open in a web browser instead of the app window")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser or native window")
    args = parser.parse_args()

    settings = load_settings()
    host = args.host or settings.host
    requested = args.port or settings.port
    port = find_free_port(host, requested)
    url = f"http://{host}:{port}"
    print("", flush=True)
    print(f"  NOVA is starting: {url}", flush=True)
    print("  Leave this window open. Close it to stop NOVA.", flush=True)
    print("", flush=True)
    logging.info("Serving %s", url)

    use_native = not args.browser and not args.no_browser
    server_thread = None
    if use_native:
        server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"),
            daemon=True,
        )
        server_thread.start()
        health = url.rstrip("/") + "/health"
        for _ in range(80):
            try:
                urllib.request.urlopen(health, timeout=0.5)
                break
            except Exception:
                time.sleep(0.15)
        try:
            from jarvis.window import wait_and_start

            wait_and_start(url)
            return
        except Exception:
            logging.exception("Native window failed, opening browser")
    if settings.open_browser and not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    if server_thread is not None:
        server_thread.join()
        return
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _setup_logging()
        logging.exception("NOVA crashed")
        print("\nNOVA failed. See data\\nova.log\n", flush=True)
        traceback.print_exc()
        sys.exit(1)
