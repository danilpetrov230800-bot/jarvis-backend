from __future__ import annotations

import logging
import sys
from typing import Any

log = logging.getLogger("nova.window")


class NovaBridge:
    def set_widget(self, enabled: bool = True) -> dict[str, Any]:
        try:
            import webview
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        windows = getattr(webview, "windows", [])
        if not windows:
            return {"ok": False, "error": "no window"}
        window = windows[0]
        enabled = bool(enabled)
        try:
            window.on_top = enabled
        except Exception:
            pass
        if enabled:
            window.resize(240, 280)
            try:
                window.move(40, 40)
            except Exception:
                pass
        else:
            window.resize(1280, 820)
        return {"ok": True, "widget": enabled}


def open_window(url: str) -> None:
    try:
        import webview
    except Exception:
        log.exception("pywebview missing")
        raise
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    except Exception:
        pass
    webview.create_window(
        "NOVA",
        url,
        width=1280,
        height=820,
        min_size=(420, 520),
        background_color="#070A12",
        text_select=True,
        js_api=NovaBridge(),
    )
    gui = "edgechromium" if sys.platform == "win32" else None
    try:
        webview.start(gui=gui)
    except Exception:
        webview.start()
