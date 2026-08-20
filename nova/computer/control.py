from __future__ import annotations

import ctypes
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from nova.paths import screenshots_dir
from nova.tools.base import ToolResult

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def _win() -> bool:
    return sys.platform == "win32"


def _key(vk: int, times: int = 1) -> None:
    if not _win():
        raise RuntimeError("windows-only")
    user32 = ctypes.windll.user32
    for _ in range(max(1, times)):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)


async def volume_up(**_: Any) -> ToolResult:
    _key(VK_VOLUME_UP, 4)
    return ToolResult(True, "Громкость выше.")


async def volume_down(**_: Any) -> ToolResult:
    _key(VK_VOLUME_DOWN, 4)
    return ToolResult(True, "Громкость ниже.")


async def volume_mute(**_: Any) -> ToolResult:
    _key(VK_VOLUME_MUTE)
    return ToolResult(True, "Звук переключён.")


async def media_play(**_: Any) -> ToolResult:
    _key(VK_MEDIA_PLAY_PAUSE)
    return ToolResult(True, "Пауза / воспроизведение.")


async def media_next(**_: Any) -> ToolResult:
    _key(VK_MEDIA_NEXT)
    return ToolResult(True, "Следующий трек.")


async def media_prev(**_: Any) -> ToolResult:
    _key(VK_MEDIA_PREV)
    return ToolResult(True, "Предыдущий трек.")


async def set_brightness(value: int = 70, **_: Any) -> ToolResult:
    if not _win():
        return ToolResult(False, "Яркость доступна в Windows.")
    percent = max(0, min(100, int(value)))
    script = (
        "$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods "
        "-ErrorAction SilentlyContinue; "
        f"if ($b) {{ $b.WmiSetBrightness(1, {percent}) }}"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=10)
    return ToolResult(True, f"Яркость примерно {percent}%.")


async def lock_pc(**_: Any) -> ToolResult:
    if not _win():
        return ToolResult(False, "Блокировка доступна в Windows.")
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return ToolResult(True, "Блокирую компьютер.")


async def type_text(text: str = "", **_: Any) -> ToolResult:
    if not _win():
        return ToolResult(False, "Ввод текста доступен в Windows.")
    escaped = text.replace("{", "{{").replace("}", "}}")
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"$w = New-Object -ComObject WScript.Shell; $w.SendKeys('{escaped}')"],
        timeout=8,
    )
    return ToolResult(True, "Текст введён.")


async def mouse_click(x: int = 0, y: int = 0, **_: Any) -> ToolResult:
    if not _win():
        return ToolResult(False, "Управление мышью доступно в Windows.")
    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return ToolResult(True, f"Клик по {x},{y}.")


async def take_screenshot(**_: Any) -> ToolResult:
    dest = screenshots_dir() / f"screen-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    if _win():
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
            "$img = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($img); "
            "$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $img.Size); "
            f"$img.Save('{dest.as_posix()}')"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], timeout=15)
    else:
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab()
            image.save(dest)
        except Exception:
            dest.write_bytes(b"")
    if dest.exists() and dest.stat().st_size > 32:
        return ToolResult(True, f"Скриншот сохранён: {dest}", {"path": str(dest)})
    return ToolResult(False, "Не удалось сделать снимок экрана.")


async def ocr_screen(**_: Any) -> ToolResult:
    shot = await take_screenshot()
    if not shot.ok:
        return shot
    path = Path(shot.data["path"])
    if _win():
        script = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {{ '' }} else {{
  $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync('{path}').GetAwaiter().GetResult()
}}
"""
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        text = (result.stdout or "").strip()
        if text:
            return ToolResult(True, f"На экране: {text[:1500]}", {"text": text, "path": str(path)})
    return ToolResult(True, f"Снимок экрана готов: {path}. Распознавание текста на этой системе недоступно.", {"path": str(path), "text": ""})


async def active_window(**_: Any) -> ToolResult:
    if not _win():
        return ToolResult(True, "Активное окно доступно в Windows.", {"title": ""})
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value or "неизвестно"
    return ToolResult(True, f"Активное окно: {title}", {"title": title})
