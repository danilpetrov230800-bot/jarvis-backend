from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Any

from jarvis.core import safe_user_path
from jarvis.storage import audit

MAX_READ_BYTES = 2 * 1024 * 1024
MAX_RESULTS = 500


def find_files(root: str, pattern: str = "*", content: str = "") -> list[dict[str, Any]]:
    base = safe_user_path(root, permission="READ_FILES")
    if not base.is_dir():
        raise ValueError("Папка не найдена")
    results: list[dict[str, Any]] = []
    for path in base.rglob(pattern or "*"):
        if not path.is_file():
            continue
        if content:
            try:
                if content.casefold() not in path.read_text(encoding="utf-8", errors="ignore").casefold():
                    continue
            except OSError:
                continue
        stat = path.stat()
        results.append({"path": str(path), "size": stat.st_size, "modified": stat.st_mtime})
        if len(results) >= MAX_RESULTS:
            break
    audit("files_searched", f"root={base.name}; count={len(results)}", category="TOOL")
    return results


def read_text(path: str) -> str:
    target = safe_user_path(path, permission="READ_FILES")
    if not target.is_file() or target.stat().st_size > MAX_READ_BYTES:
        raise ValueError("Файл не найден или слишком велик")
    return target.read_text(encoding="utf-8", errors="replace")


def write_text(path: str, content: str, *, overwrite: bool = False) -> dict[str, Any]:
    target = safe_user_path(path, permission="WRITE_FILES")
    if target.exists() and not overwrite:
        raise ValueError("Файл уже существует; подтвердите перезапись")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    audit("file_written", target.name, category="TOOL")
    return {"path": str(target), "size": target.stat().st_size}


def copy_or_move(source: str, destination: str, *, move: bool = False) -> dict[str, str]:
    src = safe_user_path(source, permission="WRITE_FILES")
    dst = safe_user_path(destination, permission="WRITE_FILES")
    if not src.exists() or dst.exists():
        raise ValueError("Источник не найден или назначение уже существует")
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = shutil.move(str(src), str(dst)) if move else shutil.copy2(src, dst)
    audit("file_moved" if move else "file_copied", f"{src.name}->{dst.name}", category="TOOL")
    return {"path": str(result)}


def archive(paths: list[str], destination: str) -> dict[str, Any]:
    if not paths or len(paths) > MAX_RESULTS:
        raise ValueError("Выберите от 1 до 500 файлов")
    target = safe_user_path(destination, permission="WRITE_FILES")
    if target.exists():
        raise ValueError("Архив уже существует")
    files = [safe_user_path(item, permission="READ_FILES") for item in paths]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for path in files:
            if path.is_file():
                output.write(path, path.name)
    audit("archive_created", target.name, category="TOOL")
    return {"path": str(target), "size": target.stat().st_size}


def duplicate_groups(root: str) -> list[list[str]]:
    files = find_files(root)
    by_size: dict[int, list[Path]] = {}
    for item in files:
        by_size.setdefault(int(item["size"]), []).append(Path(item["path"]))
    groups: list[list[str]] = []
    for candidates in by_size.values():
        if len(candidates) < 2:
            continue
        hashes: dict[str, list[str]] = {}
        for path in candidates:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(str(path))
        groups.extend(group for group in hashes.values() if len(group) > 1)
    return groups


def delete(path: str, *, confirmed: bool) -> dict[str, str]:
    if not confirmed:
        raise ValueError("Удаление требует явного подтверждения")
    target = safe_user_path(path, permission="DELETE_FILES")
    if not target.exists():
        raise ValueError("Файл не найден")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    audit("file_deleted", target.name, level="WARNING", category="SECURITY")
    return {"status": "deleted"}
