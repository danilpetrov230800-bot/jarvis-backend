from __future__ import annotations

import logging
import sys
from typing import Any

log = logging.getLogger(__name__)


class NovaBridge:
    def set_widget(self, enabled: bool = True) -> dict[str, Any]:
        try:
            import webview
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}
        windows = getattr(webview, "windows", [])
        if not windows:
            return {"ok": False, "error": "no window"}
        window = windows[0]
        enabled = bool(enabled)
        try:
            window.on_top = enabled
        except Exception:
            log.debug("on_top not supported")
        if enabled:
            window.resize(190, 220)
            try:
                window.move(40, 40)
            except Exception:
                pass
        else:
            window.resize(1120, 740)
        return {"ok": True, "widget": enabled}


def wait_and_start(url: str) -> None:
    try:
        import webview
    except Exception:
        log.exception("pywebview is not installed")
        raise
    bridge = NovaBridge()
    webview.create_window(
        "NOVA",
        url,
        width=1120,
        height=740,
        min_size=(180, 180),
        background_color="#07040f",
        text_select=True,
        js_api=bridge,
    )
    gui = "edgechromium" if sys.platform == "win32" else None
    try:
        webview.start(gui=gui)
    except Exception:
        webview.start()
