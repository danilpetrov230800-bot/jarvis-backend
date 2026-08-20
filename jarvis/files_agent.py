from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path

from jarvis.config import DATA_DIR
from jarvis.permissions import allowed, deny_message

SKIP_DIRS = {".git", "node_modules", "__pycache__", "runtime", "AppData"}


def user_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Videos",
        DATA_DIR,
    ]
    return [path for path in roots if path.exists()]


def _safe(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    for root in user_roots():
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise PermissionError("путь вне разрешённых папок пользователя")


def find_files(query: str, limit: int = 40) -> list[dict[str, str]]:
    if not allowed("READ_FILES"):
        raise PermissionError(deny_message("READ_FILES"))
    needle = query.strip().lower()
    if not needle:
        return []
    found: list[dict[str, str]] = []
    for root in user_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            for name in filenames:
                if needle in name.lower() or needle in Path(name).suffix.lower().lstrip("."):
                    path = Path(dirpath) / name
                    found.append({"name": name, "path": str(path), "size": str(path.stat().st_size)})
                    if len(found) >= limit:
                        return found
    return found


def create_file(rel_name: str, content: str = "") -> Path:
    if not allowed("WRITE_FILES"):
        raise PermissionError(deny_message("WRITE_FILES"))
    name = Path(rel_name).name
    if not name or name in {".", ".."}:
        raise ValueError("некорректное имя")
    folder = Path.home() / "Documents"
    if not folder.exists():
        folder = DATA_DIR
    path = _safe(folder / name)
    path.write_text(content, encoding="utf-8")
    return path


def delete_file(raw_path: str, confirm: bool = False) -> str:
    if not allowed("DELETE_FILES"):
        raise PermissionError(deny_message("DELETE_FILES"))
    if not confirm:
        return "Нужно подтверждение. Повторите с confirm=true."
    path = _safe(Path(raw_path))
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return f"Удалено: {path}"


def make_zip(query: str, dest_name: str = "nova-files.zip") -> Path:
    if not allowed("WRITE_FILES"):
        raise PermissionError(deny_message("WRITE_FILES"))
    files = find_files(query, limit=30)
    dest = _safe((Path.home() / "Documents" / dest_name) if (Path.home() / "Documents").exists() else DATA_DIR / dest_name)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            path = Path(item["path"])
            archive.write(path, arcname=path.name)
    return dest


def rename_file(raw_path: str, new_name: str) -> str:
    if not allowed("WRITE_FILES"):
        raise PermissionError(deny_message("WRITE_FILES"))
    path = _safe(Path(raw_path))
    dest = _safe(path.with_name(Path(new_name).name))
    path.rename(dest)
    return f"Переименовано: {dest}"


def handle_file_intent(text: str) -> dict[str, object] | None:
    lowered = text.strip().lower()
    created = re.match(r"^(?:создай|создать)\s+файл\s+(.+)$", text.strip(), re.I)
    if created:
        path = create_file(created.group(1).strip().strip("«»\""), "")
        return {"reply": f"Файл создан: {path}", "tools": ["files"]}
    found = re.match(r"^(?:найди|найти|покажи)\s+файл(?:ы)?\s+(.+)$", text.strip(), re.I)
    if found or re.search(r"найди все (pdf|jpg|png|docx|txt)", lowered):
        query = found.group(1) if found else re.search(r"(pdf|jpg|png|docx|txt)", lowered).group(1)
        items = find_files(query)
        if not items:
            return {"reply": f"Файлов по запросу «{query}» не нашла в Документах, Загрузках и на Рабочем столе.", "tools": ["files"]}
        lines = [f"Нашла {len(items)} файл(ов):"] + [f"— {row['name']} ({row['path']})" for row in items[:12]]
        return {"reply": "\n".join(lines), "tools": ["files"], "files": items}
    zipped = re.match(r"^(?:сделай|создай)\s+архив\s+(.+)$", text.strip(), re.I)
    if zipped or "сделай архив" in lowered:
        query = zipped.group(1).strip() if zipped else "pdf"
        dest = make_zip(query)
        return {"reply": f"Архив: {dest}", "tools": ["files"]}
    renamed = re.match(r"^переименуй\s+(.+?)\s+в\s+(.+)$", text.strip(), re.I)
    if renamed:
        return {"reply": rename_file(renamed.group(1).strip().strip("«»\""), renamed.group(2).strip().strip("«»\"")), "tools": ["files"]}
    deleted = re.match(r"^(?:удали|удалить)\s+файл\s+(.+)$", text.strip(), re.I)
    if deleted:
        path = deleted.group(1).strip().strip("«»\"")
        confirm = "подтверд" in lowered or "confirm" in lowered
        return {"reply": delete_file(path, confirm=confirm), "tools": ["files"], "needs_confirm": not confirm, "path": path}
    if "дубликат" in lowered:
        return {"reply": "Поиск дубликатов: сравните имена в результатах поиска файлов. Массовое удаление только с подтверждением.", "tools": ["files"]}
    return None
