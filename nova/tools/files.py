from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from nova.errors import ConfirmationRequired
from nova.paths import data_dir
from nova.permissions import PermissionService
from nova.tools.base import ToolResult

TEXT_EXT = {".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".toml", ".yml", ".yaml", ".xml", ".html", ".css", ".js"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"}
MAX_READ = 200_000


def _home() -> Path:
    return Path.home()


def resolve_user_path(raw: str, *, must_exist: bool = False) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _home() / path
    resolved = path.resolve()
    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def _is_dangerous_delete(path: Path) -> bool:
    forbidden = [
        Path(path.anchor) if path.anchor else Path("/"),
        Path.home(),
        Path("C:/Windows") if os.name == "nt" else Path("/usr"),
        Path("C:/Windows/System32") if os.name == "nt" else Path("/bin"),
    ]
    return any(path == item or path in item.parents and path == item for item in forbidden) or path == Path(path.anchor or "/")


async def find_files(query: str = "", root: str = "", extension: str = "", month: str = "", **_: Any) -> ToolResult:
    base = resolve_user_path(root) if root else _home()
    if not base.exists():
        return ToolResult(False, "Папка не найдена.")
    matches: list[str] = []
    query_l = query.lower()
    ext = extension.lower().lstrip(".")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")][:80]
        for name in filenames:
            path = Path(dirpath) / name
            if ext and path.suffix.lower().lstrip(".") != ext and f".{ext}" not in name.lower():
                if ext == "pdf" and path.suffix.lower() != ".pdf":
                    continue
                if ext == "photo" and path.suffix.lower() not in IMAGE_EXT:
                    continue
            hay = str(path).lower()
            if query_l and query_l not in hay and query_l not in name.lower():
                continue
            if month:
                try:
                    mtime = datetime.fromtimestamp(path.stat().st_mtime)
                    if f"{mtime.month:02d}" not in month and str(mtime.month) not in month:
                        continue
                except OSError:
                    continue
            matches.append(str(path))
            if len(matches) >= 80:
                break
        if len(matches) >= 80:
            break
    if not matches:
        return ToolResult(True, "Ничего не нашла по этому запросу.", {"files": []})
    preview = "\n".join(matches[:20])
    return ToolResult(True, f"Нашла {len(matches)} файл(ов):\n{preview}", {"files": matches})


async def read_file(path: str = "", **_: Any) -> ToolResult:
    target = resolve_user_path(path, must_exist=True)
    if target.suffix.lower() not in TEXT_EXT and target.stat().st_size > 64_000:
        return ToolResult(False, "Этот файл слишком большой или не текстовый.")
    data = target.read_bytes()[:MAX_READ]
    text = data.decode("utf-8", errors="replace")
    return ToolResult(True, text[:8000], {"path": str(target), "size": target.stat().st_size})


async def write_file(path: str = "", content: str = "", **_: Any) -> ToolResult:
    target = resolve_user_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult(True, f"Файл сохранён: {target}", {"path": str(target)})


async def create_file(path: str = "", content: str = "", **_: Any) -> ToolResult:
    return await write_file(path=path, content=content)


async def rename_file(path: str = "", new_name: str = "", **_: Any) -> ToolResult:
    target = resolve_user_path(path, must_exist=True)
    dest = target.with_name(new_name) if new_name else target
    target.rename(dest)
    return ToolResult(True, f"Переименовала: {dest}", {"path": str(dest)})


async def copy_file(path: str = "", destination: str = "", **_: Any) -> ToolResult:
    src = resolve_user_path(path, must_exist=True)
    dest = resolve_user_path(destination)
    if dest.is_dir() or destination.endswith(("/", "\\")):
        dest.mkdir(parents=True, exist_ok=True)
        dest = dest / src.name
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return ToolResult(True, f"Скопировала в {dest}", {"path": str(dest)})


async def move_file(path: str = "", destination: str = "", **_: Any) -> ToolResult:
    src = resolve_user_path(path, must_exist=True)
    dest = resolve_user_path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return ToolResult(True, f"Переместила в {dest}", {"path": str(dest)})


async def delete_file(path: str = "", confirmed: bool = False, permissions: PermissionService | None = None, **_: Any) -> ToolResult:
    target = resolve_user_path(path, must_exist=True)
    if _is_dangerous_delete(target):
        return ToolResult(False, "Нельзя удалять системные папки.")
    if not confirmed and permissions is not None:
        permissions.require_confirmation(
            "delete_file",
            f"Удалить {target}?",
            {"path": str(target)},
        )
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return ToolResult(True, f"Удалила {target}", {"path": str(target)})


async def list_dir(path: str = "", **_: Any) -> ToolResult:
    target = resolve_user_path(path or str(_home()))
    if not target.exists():
        return ToolResult(False, "Папка не найдена.")
    items = []
    for child in sorted(target.iterdir())[:200]:
        items.append({"name": child.name, "path": str(child), "is_dir": child.is_dir()})
    return ToolResult(True, "\n".join(f"{'[папка]' if i['is_dir'] else '[файл]'} {i['name']}" for i in items[:40]), {"items": items})


async def search_content(query: str = "", root: str = "", **_: Any) -> ToolResult:
    base = resolve_user_path(root) if root else _home()
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")][:40]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in TEXT_EXT or path.stat().st_size > 1_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if query.lower() in text.lower():
                hits.append(str(path))
            if len(hits) >= 30:
                break
        if len(hits) >= 30:
            break
    if not hits:
        return ToolResult(True, "Совпадений по содержимому нет.", {"files": []})
    return ToolResult(True, "Нашла текст в:\n" + "\n".join(hits[:15]), {"files": hits})


async def archive_paths(paths: list[str] | None = None, archive: str = "", **_: Any) -> ToolResult:
    files = [resolve_user_path(p, must_exist=True) for p in (paths or [])]
    if not files:
        return ToolResult(False, "Нужны файлы для архива.")
    dest = resolve_user_path(archive) if archive else data_dir() / f"archive-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            if item.is_dir():
                for child in item.rglob("*"):
                    if child.is_file():
                        zf.write(child, arcname=str(child.relative_to(item.parent)))
            else:
                zf.write(item, arcname=item.name)
    return ToolResult(True, f"Архив: {dest}", {"path": str(dest)})


async def extract_archive(path: str = "", destination: str = "", **_: Any) -> ToolResult:
    src = resolve_user_path(path, must_exist=True)
    dest = resolve_user_path(destination) if destination else src.parent / src.stem
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src, "r") as zf:
        for info in zf.infolist():
            name = Path(info.filename)
            if name.is_absolute() or ".." in name.parts:
                return ToolResult(False, "Архив содержит небезопасные пути.")
        zf.extractall(dest)
    return ToolResult(True, f"Распаковала в {dest}", {"path": str(dest)})


async def find_duplicates(root: str = "", **_: Any) -> ToolResult:
    base = resolve_user_path(root) if root else _home() / "Downloads"
    hashes: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")][:40]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if path.stat().st_size > 50_000_000:
                    continue
                digest = hashlib.md5(path.read_bytes()[: 1024 * 1024]).hexdigest()
            except OSError:
                continue
            hashes.setdefault(digest, []).append(str(path))
    dupes = [v for v in hashes.values() if len(v) > 1]
    if not dupes:
        return ToolResult(True, "Явных дубликатов не нашла.", {"groups": []})
    lines = ["Похожие файлы:"]
    for group in dupes[:10]:
        lines.append(" / ".join(group[:4]))
    return ToolResult(True, "\n".join(lines), {"groups": dupes})
