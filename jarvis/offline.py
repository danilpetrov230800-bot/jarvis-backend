from __future__ import annotations

import threading
import time
import urllib.request

_lock = threading.Lock()
_cached: tuple[float, bool] | None = None
_TTL = 30.0
_PROBES = ("https://1.1.1.1", "https://ya.ru")


def _probe() -> bool:
    for url in _PROBES:
        try:
            urllib.request.urlopen(url, timeout=0.6)
            return False
        except Exception:
            continue
    return True


def _refresh() -> None:
    global _cached
    offline = _probe()
    with _lock:
        _cached = (time.monotonic(), offline)


def is_offline(force: bool = False) -> bool:
    global _cached
    with _lock:
        now = time.monotonic()
        if _cached and not force and now - _cached[0] < _TTL:
            return _cached[1]
        last = _cached[1] if _cached else False
        stale = _cached is not None
    if force or not stale:
        offline = _probe()
        with _lock:
            _cached = (time.monotonic(), offline)
        return offline
    threading.Thread(target=_refresh, daemon=True).start()
    return last


def status_label(offline: bool | None = None) -> str:
    if offline is None:
        offline = is_offline()
    return "офлайн" if offline else "онлайн"
