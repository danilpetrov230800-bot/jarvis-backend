"""Управление ПК: громкость, яркость, медиа, статус системы.

Кроссплатформенно (Linux / macOS / Windows). На машине без нужного
железа/утилит методы возвращают ok=False с понятным сообщением, а не падают.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Optional

OS = platform.system()  # 'Linux' | 'Darwin' | 'Windows'


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


def _result(ok: bool, message: str, **data) -> dict:
    return {"ok": ok, "message": message, "os": OS, **data}


# --------------------------------------------------------------------------
# Громкость
# --------------------------------------------------------------------------
def set_volume(percent: int) -> dict:
    percent = max(0, min(100, int(percent)))
    if OS == "Linux":
        if _has("pactl"):
            _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            code, _ = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"])
            if code == 0:
                return _result(True, f"Громкость установлена на {percent}%.", volume=percent)
        if _has("amixer"):
            code, _ = _run(["amixer", "-q", "sset", "Master", f"{percent}%", "unmute"])
            if code == 0:
                return _result(True, f"Громкость установлена на {percent}%.", volume=percent)
        return _result(False, "На этом устройстве нет аудио-утилит (pactl/amixer).")
    if OS == "Darwin":
        code, _ = _run(["osascript", "-e", f"set volume output volume {percent}"])
        return _result(code == 0, f"Громкость установлена на {percent}%." if code == 0 else "Не удалось.", volume=percent)
    if OS == "Windows":
        if _has("nircmd"):
            code, _ = _run(["nircmd", "setsysvolume", str(int(percent / 100 * 65535))])
            return _result(code == 0, f"Громкость установлена на {percent}%.", volume=percent)
        return _result(False, "Для Windows нужен nircmd.exe в PATH.")
    return _result(False, "Неизвестная ОС.")


def get_volume() -> dict:
    if OS == "Linux" and _has("pactl"):
        code, out = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        m = re.search(r"(\d+)%", out)
        if code == 0 and m:
            return _result(True, f"Текущая громкость: {m.group(1)}%.", volume=int(m.group(1)))
    if OS == "Darwin":
        code, out = _run(["osascript", "-e", "output volume of (get volume settings)"])
        if code == 0 and out.strip().isdigit():
            return _result(True, f"Текущая громкость: {out.strip()}%.", volume=int(out.strip()))
    return _result(False, "Не удалось прочитать громкость на этом устройстве.")


def mute(state: bool = True) -> dict:
    if OS == "Linux" and _has("pactl"):
        code, _ = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if state else "0"])
        return _result(code == 0, "Звук выключен." if state else "Звук включён.")
    if OS == "Darwin":
        code, _ = _run(["osascript", "-e", f"set volume {'with' if not state else 'without'} output muted"])
        return _result(code == 0, "Звук выключен." if state else "Звук включён.")
    return _result(False, "Управление отключением звука недоступно.")


# --------------------------------------------------------------------------
# Яркость
# --------------------------------------------------------------------------
def set_brightness(percent: int) -> dict:
    percent = max(5, min(100, int(percent)))
    if OS == "Linux":
        if _has("brightnessctl"):
            code, _ = _run(["brightnessctl", "set", f"{percent}%"])
            if code == 0:
                return _result(True, f"Яркость установлена на {percent}%.", brightness=percent)
        if _has("xbacklight"):
            code, _ = _run(["xbacklight", "-set", str(percent)])
            if code == 0:
                return _result(True, f"Яркость установлена на {percent}%.", brightness=percent)
        return _result(False, "Нет утилит яркости (brightnessctl/xbacklight) или дисплея.")
    if OS == "Darwin":
        if _has("brightness"):
            code, _ = _run(["brightness", str(percent / 100)])
            return _result(code == 0, f"Яркость установлена на {percent}%.", brightness=percent)
        return _result(False, "Для macOS установите CLI `brightness` (brew install brightness).")
    if OS == "Windows":
        ps = (
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
            f".WmiSetBrightness(1,{percent})"
        )
        code, _ = _run(["powershell", "-NoProfile", "-Command", ps])
        return _result(code == 0, f"Яркость установлена на {percent}%.", brightness=percent)
    return _result(False, "Неизвестная ОС.")


# --------------------------------------------------------------------------
# Медиа (play/pause/next/prev)
# --------------------------------------------------------------------------
def media(action: str) -> dict:
    action = action.lower()
    mapping_linux = {"play": "play-pause", "pause": "play-pause", "next": "next", "prev": "previous"}
    if OS == "Linux" and _has("playerctl"):
        code, _ = _run(["playerctl", mapping_linux.get(action, "play-pause")])
        return _result(code == 0, f"Медиа: {action}.")
    if OS == "Darwin":
        keymap = {"play": 16, "pause": 16, "next": 17, "prev": 18}
        code, _ = _run(["osascript", "-e",
                        f'tell application "System Events" to key code {keymap.get(action, 16)}'])
        return _result(code == 0, f"Медиа: {action}.")
    return _result(False, "Медиа-управление недоступно на этом устройстве.")


# --------------------------------------------------------------------------
# Питание (безопасные действия)
# --------------------------------------------------------------------------
def power(action: str) -> dict:
    action = action.lower()
    cmds = {
        "Linux": {
            "lock": ["loginctl", "lock-session"],
            "sleep": ["systemctl", "suspend"],
        },
        "Darwin": {
            "lock": ["pmset", "displaysleepnow"],
            "sleep": ["pmset", "sleepnow"],
        },
        "Windows": {
            "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
        },
    }
    cmd = cmds.get(OS, {}).get(action)
    if not cmd:
        return _result(False, f"Действие «{action}» недоступно на {OS}.")
    code, _ = _run(cmd)
    return _result(code == 0, f"Выполнено: {action}." if code == 0 else f"Не удалось: {action}.")


# --------------------------------------------------------------------------
# Статус системы (psutil)
# --------------------------------------------------------------------------
def status() -> dict:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        data = {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / 1e9, 1),
            "ram_total_gb": round(mem.total / 1e9, 1),
            "cores": psutil.cpu_count(),
        }
        try:
            batt = psutil.sensors_battery()
            if batt:
                data["battery_percent"] = round(batt.percent)
                data["charging"] = batt.power_plugged
        except Exception:
            pass
        try:
            data["disk_percent"] = psutil.disk_usage("/").percent
        except Exception:
            pass
        msg = (
            f"CPU {cpu:.0f}%, RAM {mem.percent:.0f}% "
            f"({data['ram_used_gb']}/{data['ram_total_gb']} ГБ)"
        )
        if "battery_percent" in data:
            msg += f", батарея {data['battery_percent']}%"
        return _result(True, msg, **data)
    except Exception as e:  # noqa: BLE001
        return _result(False, f"Не удалось получить статус: {e}")
