from __future__ import annotations

import subprocess
import sys
from typing import Any

from nova.tools.base import ToolResult


def _win() -> bool:
    return sys.platform == "win32"


async def get_clipboard(**_: Any) -> ToolResult:
    if _win():
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        text = (result.stdout or "").strip()
        return ToolResult(True, text or "Буфер обмена пуст.", {"text": text})
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return ToolResult(True, text or "Буфер обмена пуст.", {"text": text})
    except Exception:
        return ToolResult(True, "Буфер обмена недоступен.", {"text": ""})


async def set_clipboard(text: str = "", **_: Any) -> ToolResult:
    if _win():
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            timeout=8,
        )
        return ToolResult(True, "Скопировала в буфер обмена.")
    return ToolResult(False, "Запись в буфер доступна в Windows.")
