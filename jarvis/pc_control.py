from __future__ import annotations

import ctypes
import subprocess
import sys
from dataclasses import dataclass

from jarvis.permissions import require

@dataclass
class PcState:
    reply: str
    tools: list[str]


VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1


def _win() -> bool:
    return sys.platform == "win32"


def _key(virtual_key: int, times: int = 1) -> None:
    if not _win():
        raise RuntimeError("управление ПК доступно в Windows")
    for _ in range(max(1, times)):
        ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(virtual_key, 0, 2, 0)


def volume_up(steps: int = 4) -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_VOLUME_UP, steps)
    return "Громкость выше."


def volume_down(steps: int = 4) -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_VOLUME_DOWN, steps)
    return "Громкость ниже."


def volume_mute() -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_VOLUME_MUTE)
    return "Звук переключён (mute)."


def media_play_pause() -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_MEDIA_PLAY_PAUSE)
    return "Пауза / воспроизведение."


def media_next() -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_MEDIA_NEXT)
    return "Следующий трек."


def media_prev() -> str:
    require("SYSTEM_SETTINGS")
    _key(VK_MEDIA_PREV)
    return "Предыдущий трек."


def set_brightness(percent: int) -> str:
    require("SYSTEM_SETTINGS")
    if not _win():
        raise RuntimeError("яркость доступна в Windows")
    value = max(0, min(100, int(percent)))
    script = (
        "$b = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods "
        "-ErrorAction SilentlyContinue; "
        f"if ($b) {{ $b.WmiSetBrightness(1, {value}) }}"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False, capture_output=True)
    return f"Яркость примерно {value}%."


def brightness_up() -> str:
    return set_brightness(80)


def brightness_down() -> str:
    return set_brightness(30)


def open_sound_settings() -> str:
    require("SYSTEM_SETTINGS")
    if not _win():
        raise RuntimeError("микшер звука доступен в Windows")
    subprocess.Popen(["sndvol.exe"], close_fds=True)
    return "Открываю микшер громкости."


def open_display_settings() -> str:
    require("SYSTEM_SETTINGS")
    if not _win():
        raise RuntimeError("настройки экрана доступны в Windows")
    subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:display"], close_fds=True)
    return "Открываю настройки экрана."


def sleep_pc() -> str:
    require("SYSTEM_SETTINGS")
    if not _win():
        raise RuntimeError("сон доступен в Windows")
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return "Отправляю компьютер в сон."


def handle_pc_intent(lowered: str) -> PcState | None:
    if lowered in {"выключи звук", "без звука", "mute", "мут"}:
        return PcState(volume_mute(), ["volume"])
    if lowered in {"громче", "сделай громче", "прибавь звук"}:
        return PcState(volume_up(), ["volume"])
    if lowered in {"тише", "сделай тише", "убавь звук"}:
        return PcState(volume_down(), ["volume"])
    if "яркость" in lowered and ("повыс" in lowered or "увелич" in lowered or lowered in {"ярче", "сделай ярче"}):
        return PcState(brightness_up(), ["brightness"])
    if lowered in {"ярче", "сделай ярче"}:
        return PcState(brightness_up(), ["brightness"])
    if lowered in {"темнее", "сделай темнее", "приглуши"}:
        return PcState(brightness_down(), ["brightness"])
    if "яркость" in lowered:
        digits = "".join(ch for ch in lowered if ch.isdigit())
        if digits:
            return PcState(set_brightness(int(digits)), ["brightness"])
    if lowered in {"пауза", "play", "плей", "стоп музыка", "пауза музыка"}:
        return PcState(media_play_pause(), ["media"])
    if "следующ" in lowered and ("трек" in lowered or "песн" in lowered):
        return PcState(media_next(), ["media"])
    if "предыдущ" in lowered and ("трек" in lowered or "песн" in lowered):
        return PcState(media_prev(), ["media"])
    if lowered in {"микшер", "открой микшер", "громкость настройки"}:
        return PcState(open_sound_settings(), ["volume"])
    if lowered in {"настройки экрана", "открой яркость"}:
        return PcState(open_display_settings(), ["brightness"])
    if lowered in {"сон", "усни", "усыпи компьютер", "sleep"}:
        return PcState(sleep_pc(), ["sleep"])
    return None
