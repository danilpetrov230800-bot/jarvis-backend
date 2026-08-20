from __future__ import annotations

import inspect
from typing import Any, Callable

from nova.computer import (
    active_window,
    lock_pc,
    media_next,
    media_play,
    media_prev,
    mouse_click,
    ocr_screen,
    set_brightness,
    take_screenshot,
    type_text,
    volume_down,
    volume_mute,
    volume_up,
)
from nova.errors import ConfirmationRequired, PermissionDenied
from nova.logging_service import LogService
from nova.permissions import PermissionService
from nova.tools.apps import close_app, list_apps, open_app
from nova.tools.base import ToolResult, ToolSpec
from nova.tools.calculator import calculator
from nova.tools.clipboard import get_clipboard, set_clipboard
from nova.tools.files import (
    archive_paths,
    copy_file,
    create_file,
    delete_file,
    extract_archive,
    find_duplicates,
    find_files,
    list_dir,
    move_file,
    read_file,
    rename_file,
    search_content,
    write_file,
)
from nova.intent import help_text
from nova.tools.notes import NotesTool
from nova.tools.system import diagnose_slow, disk_info, list_processes, system_info
from nova.tools.web import browse_url, get_currency, get_weather, wiki_summary, web_search


class ToolRegistry:
    def __init__(self, permissions: PermissionService, log: LogService, notes: NotesTool) -> None:
        self.permissions = permissions
        self.log = log
        self.notes = notes
        self._tools: dict[str, ToolSpec] = {}
        self._register_all()

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "title": spec.title,
                "description": spec.description,
                "permission": spec.permission,
                "dangerous": spec.dangerous,
                "offline": spec.offline,
            }
            for spec in self._tools.values()
        ]

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.schema,
                },
            }
            for spec in self._tools.values()
        ]

    async def run(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(False, f"Неизвестный инструмент: {name}").as_dict()
        try:
            self.permissions.require(spec.permission)
        except PermissionDenied as exc:
            return ToolResult(False, exc.user_message).as_dict()
        payload = dict(args or {})
        payload["permissions"] = self.permissions
        try:
            result = await spec.handler(**_filter_args(spec.handler, payload))
        except ConfirmationRequired as exc:
            return ToolResult(
                False,
                exc.summary,
                needs_confirmation=True,
                confirmation_token=exc.token,
                confirmation_summary=exc.summary,
            ).as_dict()
        except PermissionDenied as exc:
            return ToolResult(False, exc.user_message).as_dict()
        except Exception as exc:
            self.log.error("tool failed", tool=name, error=str(exc))
            return ToolResult(False, "Я не смог выполнить действие.").as_dict()
        self.log.info("tool ok", tool=name)
        self.permissions.audit("tool", "INFO", name, {"ok": result.ok})
        return result.as_dict()

    def _add(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def _register_all(self) -> None:
        def add(name, title, desc, permission, handler, schema, dangerous=False, offline=True):
            self._add(ToolSpec(name, title, desc, permission, handler, schema, dangerous, offline))

        async def local_answer(text: str = "", **_: Any) -> ToolResult:
            return ToolResult(True, help_text())

        add("local_answer", "Локальный ответ", "Ответ без внешней модели.", "READ_FILES", local_answer, {"type": "object", "properties": {"text": {"type": "string"}}})
        add("calculator", "Калькулятор", "Считать выражение.", "READ_FILES", calculator, {"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]})
        add("find_files", "Поиск файлов", "Найти файлы.", "READ_FILES", find_files, {"type": "object", "properties": {"query": {"type": "string"}, "root": {"type": "string"}, "extension": {"type": "string"}, "month": {"type": "string"}}})
        add("list_dir", "Файлы", "Список папки.", "READ_FILES", list_dir, {"type": "object", "properties": {"path": {"type": "string"}}})
        add("read_file", "Чтение файла", "Прочитать текстовый файл.", "READ_FILES", read_file, {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
        add("write_file", "Запись файла", "Создать или изменить файл.", "WRITE_FILES", write_file, {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path"]})
        add("create_file", "Создание файла", "Создать файл.", "WRITE_FILES", create_file, {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path"]})
        add("rename_file", "Переименование", "Переименовать файл.", "WRITE_FILES", rename_file, {"type": "object", "properties": {"path": {"type": "string"}, "new_name": {"type": "string"}}})
        add("copy_file", "Копирование", "Скопировать файл.", "WRITE_FILES", copy_file, {"type": "object", "properties": {"path": {"type": "string"}, "destination": {"type": "string"}}})
        add("move_file", "Перемещение", "Переместить файл.", "WRITE_FILES", move_file, {"type": "object", "properties": {"path": {"type": "string"}, "destination": {"type": "string"}}})
        add("delete_file", "Удаление", "Удалить файл после подтверждения.", "DELETE_FILES", delete_file, {"type": "object", "properties": {"path": {"type": "string"}, "confirmed": {"type": "boolean"}}}, dangerous=True)
        add("search_content", "Поиск по содержимому", "Найти текст в файлах.", "READ_FILES", search_content, {"type": "object", "properties": {"query": {"type": "string"}, "root": {"type": "string"}}})
        add("archive", "Архив", "Собрать ZIP.", "WRITE_FILES", archive_paths, {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}, "archive": {"type": "string"}}})
        add("extract_archive", "Распаковка", "Распаковать ZIP.", "WRITE_FILES", extract_archive, {"type": "object", "properties": {"path": {"type": "string"}, "destination": {"type": "string"}}})
        add("find_duplicates", "Дубликаты", "Найти похожие файлы.", "READ_FILES", find_duplicates, {"type": "object", "properties": {"root": {"type": "string"}}})
        add("system_info", "Система", "CPU, RAM, диск, версия Windows.", "READ_FILES", system_info, {"type": "object", "properties": {}})
        add("list_processes", "Процессы", "Активные процессы.", "READ_FILES", list_processes, {"type": "object", "properties": {"limit": {"type": "integer"}}})
        add("diagnose_slow", "Почему тормозит", "Анализ нагрузки.", "READ_FILES", diagnose_slow, {"type": "object", "properties": {}})
        add("disk_info", "Диски", "Свободное место.", "READ_FILES", disk_info, {"type": "object", "properties": {}})
        add("open_app", "Запуск приложения", "Открыть программу.", "RUN_APPLICATIONS", open_app, {"type": "object", "properties": {"name": {"type": "string"}}})
        add("close_app", "Закрытие приложения", "Закрыть программу.", "RUN_APPLICATIONS", close_app, {"type": "object", "properties": {"name": {"type": "string"}}}, dangerous=True)
        add("list_apps", "Приложения", "Индекс установленных программ.", "RUN_APPLICATIONS", list_apps, {"type": "object", "properties": {}})
        add("clipboard_get", "Буфер", "Прочитать буфер обмена.", "CLIPBOARD", get_clipboard, {"type": "object", "properties": {}})
        add("clipboard_set", "Буфер", "Записать в буфер.", "CLIPBOARD", set_clipboard, {"type": "object", "properties": {"text": {"type": "string"}}})
        add("save_note", "Заметка", "Сохранить заметку.", "WRITE_FILES", self.notes.save, {"type": "object", "properties": {"text": {"type": "string"}}})
        add("list_notes", "Заметки", "Показать заметки.", "READ_FILES", self.notes.list, {"type": "object", "properties": {}})
        add("web_search", "Поиск", "Открытый интернет.", "NETWORK", web_search, {"type": "object", "properties": {"query": {"type": "string"}}}, offline=False)
        add("browse_url", "Страница", "Прочитать публичную страницу.", "NETWORK", browse_url, {"type": "object", "properties": {"url": {"type": "string"}}}, offline=False)
        add("get_weather", "Погода", "Погода по городу.", "NETWORK", get_weather, {"type": "object", "properties": {"location": {"type": "string"}}}, offline=False)
        add("get_currency", "Курс", "Курс ЦБ.", "NETWORK", get_currency, {"type": "object", "properties": {}}, offline=False)
        add("wiki_summary", "Википедия", "Краткая статья.", "NETWORK", wiki_summary, {"type": "object", "properties": {"topic": {"type": "string"}}}, offline=False)
        add("volume_up", "Громче", "Прибавить звук.", "SYSTEM_SETTINGS", volume_up, {"type": "object", "properties": {}})
        add("volume_down", "Тише", "Убавить звук.", "SYSTEM_SETTINGS", volume_down, {"type": "object", "properties": {}})
        add("volume_mute", "Mute", "Выключить звук.", "SYSTEM_SETTINGS", volume_mute, {"type": "object", "properties": {}})
        add("media_play", "Медиа", "Пауза/плей.", "SYSTEM_SETTINGS", media_play, {"type": "object", "properties": {}})
        add("media_next", "Следующий трек", "Следующий трек.", "SYSTEM_SETTINGS", media_next, {"type": "object", "properties": {}})
        add("media_prev", "Предыдущий трек", "Предыдущий трек.", "SYSTEM_SETTINGS", media_prev, {"type": "object", "properties": {}})
        add("set_brightness", "Яркость", "Яркость экрана.", "SYSTEM_SETTINGS", set_brightness, {"type": "object", "properties": {"value": {"type": "integer"}}})
        add("lock_pc", "Блокировка", "Заблокировать ПК.", "SYSTEM_SETTINGS", lock_pc, {"type": "object", "properties": {}}, dangerous=True)
        add("type_text", "Ввод", "Ввести текст.", "SCREEN_CONTROL", type_text, {"type": "object", "properties": {"text": {"type": "string"}}})
        add("mouse_click", "Клик", "Клик мыши.", "SCREEN_CONTROL", mouse_click, {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}})
        add("screenshot", "Скриншот", "Снимок экрана.", "SCREEN_CONTROL", take_screenshot, {"type": "object", "properties": {}})
        add("ocr_screen", "OCR", "Прочитать экран.", "SCREEN_CONTROL", ocr_screen, {"type": "object", "properties": {}})
        add("active_window", "Окно", "Активное окно.", "SCREEN_CONTROL", active_window, {"type": "object", "properties": {}})


def _filter_args(handler: Callable[..., Any], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(handler)
        names = set(signature.parameters)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
            return payload
        return {k: v for k, v in payload.items() if k in names}
    except (TypeError, ValueError):
        return payload
