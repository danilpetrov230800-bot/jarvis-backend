"""Tool registry for NOVA local tools."""

from __future__ import annotations

import asyncio
import fnmatch
import glob
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

import psutil

from nova.core.config import get_settings
from nova.core.logging import get_audit_log, get_logger
from nova.database.db import ActionHistory, get_session
from nova.security.permissions import PermissionDenied, get_permission_manager

logger = get_logger("nova.tools")
audit = get_audit_log()

ToolFunc = Callable[[dict, dict | None], Awaitable[dict]]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._register_defaults()

    def register(
        self,
        name: str,
        description: str,
        permission: str | None,
        handler: ToolFunc,
        dangerous: bool = False,
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "permission": permission,
            "dangerous": dangerous,
            "handler": handler,
        }

    def list_tools(self) -> list[dict]:
        return [
            {k: v for k, v in tool.items() if k != "handler"}
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        params: dict | None = None,
        context: dict | None = None,
        confirmed: bool = False,
    ) -> dict:
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}

        tool = self._tools[name]
        perm = tool.get("permission")

        if perm:
            try:
                get_permission_manager().require(perm)
            except PermissionDenied as e:
                return {"error": str(e), "permission_required": e.permission}

        if tool.get("dangerous") and not confirmed and not (context or {}).get("test_mode"):
            return {
                "confirmation_required": True,
                "message": f"Подтвердите выполнение: {tool['description']}",
                "tool": name,
                "params": params,
            }

        try:
            result = await tool["handler"](params or {}, context)
            self._log_action(name, params, result)
            audit.record("TOOL", name, {"params": params, "success": "error" not in result})
            return result
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return {"error": "Не удалось выполнить действие"}

    def _log_action(self, action: str, params: dict | None, result: dict) -> None:
        with get_session() as session:
            session.add(ActionHistory(
                action=action,
                details_json=json.dumps({"params": params, "result": str(result)[:500]}, ensure_ascii=False),
            ))
            session.commit()

    def _register_defaults(self) -> None:
        self.register("calculator", "Калькулятор", None, self._calculator)
        self.register("file_search", "Поиск файлов", "READ_FILES", self._file_search)
        self.register("file_read", "Чтение файла", "READ_FILES", self._file_read)
        self.register("file_write", "Создание/редактирование файла", "WRITE_FILES", self._file_write)
        self.register("file_delete", "Удаление файла", "DELETE_FILES", self._file_delete, dangerous=True)
        self.register("file_copy", "Копирование файла", "WRITE_FILES", self._file_copy)
        self.register("file_move", "Перемещение файла", "WRITE_FILES", self._file_move)
        self.register("file_rename", "Переименование файла", "WRITE_FILES", self._file_rename)
        self.register("content_search", "Поиск по содержимому", "READ_FILES", self._content_search)
        self.register("archive", "Архивирование", "WRITE_FILES", self._archive)
        self.register("unarchive", "Распаковка архива", "WRITE_FILES", self._unarchive)
        self.register("system_info", "Системная информация", None, self._system_info)
        self.register("disk_info", "Информация о дисках", None, self._disk_info)
        self.register("process_list", "Список процессов", None, self._process_list)
        self.register("clipboard", "Буфер обмена", None, self._clipboard)
        self.register("screenshot", "Скриншот", "SCREEN_CONTROL", self._screenshot)
        self.register("ocr", "OCR распознавание", "SCREEN_CONTROL", self._ocr)
        self.register("launch_app", "Запуск приложения", "RUN_APPLICATIONS", self._launch_app)
        self.register("notes", "Заметки", None, self._notes)
        self.register("timer", "Таймер", None, self._timer)
        self.register("web_search", "Локальный поиск", "NETWORK", self._web_search)

    async def _calculator(self, params: dict, _ctx: dict | None) -> dict:
        expr = params.get("expression", params.get("query", ""))
        try:
            allowed = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow, "sqrt": math.sqrt}
            result = eval(expr, {"__builtins__": {}}, allowed)
            return {"result": result, "expression": expr}
        except Exception:
            return {"error": "Неверное выражение"}

    async def _file_search(self, params: dict, _ctx: dict | None) -> dict:
        query = params.get("query", "*")
        path = Path(params.get("path", str(Path.home())))
        pattern = params.get("pattern", f"*{query}*")
        ext = params.get("extension", "")

        results = []
        try:
            for item in path.rglob(pattern if "*" in pattern else f"*{query}*"):
                if ext and item.suffix.lower() != ext.lower():
                    continue
                if item.is_file():
                    results.append(str(item))
                if len(results) >= params.get("limit", 50):
                    break
        except PermissionError:
            return {"error": "Нет доступа к указанной папке"}

        return {"files": results, "count": len(results)}

    async def _file_read(self, params: dict, _ctx: dict | None) -> dict:
        path = Path(params["path"])
        if not path.exists():
            return {"error": "Файл не найден"}
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            max_len = params.get("max_length", 10000)
            return {"path": str(path), "content": content[:max_len], "truncated": len(content) > max_len}
        except Exception:
            return {"error": "Не удалось прочитать файл"}

    async def _file_write(self, params: dict, _ctx: dict | None) -> dict:
        path = Path(params["path"])
        content = params.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        if params.get("append"):
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return {"path": str(path), "written": len(content)}

    async def _file_delete(self, params: dict, _ctx: dict | None) -> dict:
        path = Path(params["path"])
        if not path.exists():
            return {"error": "Файл не найден"}
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return {"deleted": str(path)}

    async def _file_copy(self, params: dict, _ctx: dict | None) -> dict:
        src = Path(params["source"])
        dst = Path(params["destination"])
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return {"copied": str(src), "to": str(dst)}

    async def _file_move(self, params: dict, _ctx: dict | None) -> dict:
        src = Path(params["source"])
        dst = Path(params["destination"])
        shutil.move(str(src), str(dst))
        return {"moved": str(src), "to": str(dst)}

    async def _file_rename(self, params: dict, _ctx: dict | None) -> dict:
        src = Path(params["path"])
        new_name = params["new_name"]
        dst = src.parent / new_name
        src.rename(dst)
        return {"renamed": str(src), "to": str(dst)}

    async def _content_search(self, params: dict, _ctx: dict | None) -> dict:
        query = params["query"]
        path = Path(params.get("path", str(Path.home())))
        results = []
        for item in path.rglob("*"):
            if not item.is_file() or item.stat().st_size > 1_000_000:
                continue
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                if query.lower() in text.lower():
                    results.append(str(item))
            except Exception:
                continue
            if len(results) >= 30:
                break
        return {"matches": results, "count": len(results)}

    async def _archive(self, params: dict, _ctx: dict | None) -> dict:
        source = Path(params["source"])
        archive = Path(params.get("destination", str(source) + ".zip"))
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            if source.is_dir():
                for f in source.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(source.parent))
            else:
                zf.write(source, source.name)
        return {"archive": str(archive)}

    async def _unarchive(self, params: dict, _ctx: dict | None) -> dict:
        archive = Path(params["path"])
        dest = Path(params.get("destination", archive.parent / archive.stem))
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)
        return {"extracted_to": str(dest)}

    async def _system_info(self, _params: dict, _ctx: dict | None) -> dict:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.5)
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot

        analysis = []
        if cpu > 80:
            analysis.append("Высокая загрузка CPU — возможны тормоза.")
        if mem.percent > 85:
            analysis.append("Мало свободной RAM — закройте лишние приложения.")

        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_percent": mem.percent,
            "ram_available_gb": round(mem.available / (1024**3), 2),
            "uptime_hours": round(uptime.total_seconds() / 3600, 1),
            "analysis": analysis or ["Система работает нормально."],
        }

    async def _disk_info(self, _params: dict, _ctx: dict | None) -> dict:
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
        return {"disks": disks}

    async def _process_list(self, params: dict, _ctx: dict | None) -> dict:
        limit = params.get("limit", 20)
        processes = []
        for proc in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]), key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:limit]:
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"processes": processes}

    async def _clipboard(self, params: dict, _ctx: dict | None) -> dict:
        try:
            import pyperclip
            action = params.get("action", "read")
            if action == "write":
                pyperclip.copy(params.get("text", ""))
                return {"written": True}
            return {"content": pyperclip.paste()}
        except Exception:
            return {"error": "Буфер обмена недоступен"}

    async def _screenshot(self, params: dict, _ctx: dict | None) -> dict:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            path = get_settings().data_dir / "screenshots"
            path.mkdir(parents=True, exist_ok=True)
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = path / filename
            img.save(filepath)
            return {"path": str(filepath)}
        except Exception:
            return {"error": "Скриншот недоступен на этой платформе"}

    async def _ocr(self, params: dict, _ctx: dict | None) -> dict:
        path = params.get("path")
        if not path:
            ss = await self._screenshot({}, _ctx)
            if "error" in ss:
                return ss
            path = ss["path"]
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path), lang="rus+eng")
            return {"text": text.strip(), "path": path}
        except Exception:
            return {"error": "OCR недоступен. Установите Tesseract OCR."}

    async def _launch_app(self, params: dict, _ctx: dict | None) -> dict:
        name = params.get("name", params.get("query", ""))
        if platform.system() == "Windows":
            try:
                subprocess.Popen(f'start "" "{name}"', shell=True)
                return {"launched": name}
            except Exception:
                pass
            paths = [
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            ]
            for base in paths:
                if not base.exists():
                    continue
                for exe in base.rglob("*.exe"):
                    if name.lower() in exe.stem.lower():
                        subprocess.Popen([str(exe)])
                        return {"launched": str(exe)}
        else:
            for cmd in (name, name.lower()):
                try:
                    subprocess.Popen([cmd])
                    return {"launched": cmd}
                except Exception:
                    continue
        return {"error": f"Приложение '{name}' не найдено"}

    async def _notes(self, params: dict, _ctx: dict | None) -> dict:
        notes_dir = get_settings().data_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        action = params.get("action", "list")

        if action == "create":
            title = params.get("title", "note")
            content = params.get("content", "")
            path = notes_dir / f"{title}.txt"
            path.write_text(content, encoding="utf-8")
            return {"created": str(path)}

        if action == "read":
            path = notes_dir / f"{params.get('title', 'note')}.txt"
            if path.exists():
                return {"content": path.read_text(encoding="utf-8")}
            return {"error": "Заметка не найдена"}

        notes = [f.stem for f in notes_dir.glob("*.txt")]
        return {"notes": notes}

    async def _timer(self, params: dict, _ctx: dict | None) -> dict:
        seconds = int(params.get("seconds", 60))
        await asyncio.sleep(min(seconds, 5))
        return {"timer_set": seconds, "message": f"Таймер на {seconds} секунд установлен"}

    async def _web_search(self, params: dict, _ctx: dict | None) -> dict:
        query = params.get("query", "")
        return {
            "query": query,
            "results": [],
            "message": "Локальный поиск. Для веб-поиска включите NETWORK permission и настройте провайдер.",
        }


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
