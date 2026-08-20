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

from jarvis.net import find_free_port

load_dotenv(ROOT / ".env")
LOG = ROOT / "data" / "nova.log"


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
    parser.add_argument("--no-browser", action="store_true")
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
    if settings.open_browser and not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
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
