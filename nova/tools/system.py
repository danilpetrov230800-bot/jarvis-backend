from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime
from typing import Any

from nova.paths import app_root
from nova.tools.base import ToolResult

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None  # type: ignore


def _bytes(n: float) -> str:
    return f"{n / 1024 ** 3:.1f} ГБ"


async def system_info(**_: Any) -> ToolResult:
    cpu = platform.processor() or platform.machine()
    uname = platform.uname()
    disk = shutil.disk_usage(str(app_root().anchor or "/"))
    lines = [
        f"Система: {uname.system} {uname.release} ({uname.version})",
        f"Компьютер: {uname.node}",
        f"Процессор: {cpu}",
        f"Диск: свободно {_bytes(disk.free)} из {_bytes(disk.total)}",
    ]
    data: dict[str, Any] = {
        "system": uname.system,
        "release": uname.release,
        "node": uname.node,
        "cpu": cpu,
        "disk_free": disk.free,
        "disk_total": disk.total,
        "uptime": None,
        "ram": None,
        "gpu": None,
        "temperature": None,
    }
    if psutil:
        vm = psutil.virtual_memory()
        data["ram"] = {"total": vm.total, "available": vm.available, "percent": vm.percent}
        lines.append(f"Память: занято {vm.percent}% ({_bytes(vm.used)} из {_bytes(vm.total)})")
        boot = datetime.fromtimestamp(psutil.boot_time())
        data["uptime"] = str(datetime.now() - boot).split(".")[0]
        lines.append(f"Аптайм: {data['uptime']}")
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            if temps:
                first = next(iter(temps.values()))[0]
                data["temperature"] = first.current
                lines.append(f"Температура: {first.current:.0f}°C")
        except Exception:
            pass
        try:
            battery = psutil.sensors_battery()
            if battery:
                lines.append(f"Батарея: {battery.percent:.0f}%")
        except Exception:
            pass
    else:
        lines.append("Подробные датчики недоступны.")
    return ToolResult(True, "\n".join(lines), data)


async def list_processes(limit: int = 12, **_: Any) -> ToolResult:
    if not psutil:
        return ToolResult(True, "Список процессов недоступен в этой сборке.", {"processes": []})
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        info = proc.info
        procs.append(info)
    procs.sort(key=lambda p: (p.get("cpu_percent") or 0), reverse=True)
    top = procs[: max(3, min(int(limit), 25))]
    lines = ["Самые активные процессы:"]
    for item in top:
        lines.append(f"- {item.get('name')} (PID {item.get('pid')}), CPU {item.get('cpu_percent') or 0:.1f}%")
    return ToolResult(True, "\n".join(lines), {"processes": top})


async def diagnose_slow(**_: Any) -> ToolResult:
    info = await system_info()
    reasons = []
    ram = (info.data or {}).get("ram") or {}
    if ram.get("percent", 0) > 85:
        reasons.append("Память почти заполнена — из-за этого компьютер может тормозить.")
    disk_free = info.data.get("disk_free") or 0
    disk_total = info.data.get("disk_total") or 1
    if disk_free / disk_total < 0.08:
        reasons.append("На диске мало места.")
    if not reasons:
        reasons.append("Явных перегрузок не видно. Если тормозит, закройте тяжёлые программы.")
    body = info.reply + "\n\n" + "\n".join(reasons)
    return ToolResult(True, body, info.data)


async def disk_info(**_: Any) -> ToolResult:
    lines = ["Диски:"]
    items = []
    if psutil:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            items.append(
                {
                    "device": part.device,
                    "mount": part.mountpoint,
                    "free": usage.free,
                    "total": usage.total,
                }
            )
            lines.append(f"- {part.device} ({part.mountpoint}): свободно {_bytes(usage.free)} из {_bytes(usage.total)}")
    else:
        usage = shutil.disk_usage(os.path.abspath(os.sep))
        lines.append(f"свободно {_bytes(usage.free)} из {_bytes(usage.total)}")
    return ToolResult(True, "\n".join(lines), {"disks": items})
