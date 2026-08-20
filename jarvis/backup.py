from __future__ import annotations

import os
import json
import zipfile
from pathlib import Path

from jarvis.config import DATA_DIR
from jarvis.store import migrate, utc_now

SKIP = {"tts_cache", ".write-test", "backups"}


def backup_dir() -> Path:
    path = DATA_DIR / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(include_secrets: bool = False) -> Path:
    migrate()
    dest = backup_dir() / f"nova-backup-{utc_now().replace(':', '')}-{os.getpid()}-{os.urandom(2).hex()}.zip"
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in DATA_DIR.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP for part in path.parts):
                continue
            if path.name == "settings.json" and not include_secrets:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                payload["api_key"] = ""
                archive.writestr("settings.json", json.dumps(payload, ensure_ascii=False, indent=2))
                continue
            archive.write(path, arcname=path.relative_to(DATA_DIR).as_posix())
    return dest


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
            raise ValueError("небезопасный архив")
        target = (dest / name).resolve()
        if not _is_inside(target, dest) and target != dest:
            raise ValueError("небезопасный архив")
    archive.extractall(dest)


def list_backups() -> list[dict[str, str]]:
    items = []
    folder = backup_dir()
    for path in sorted(folder.glob("nova-backup-*.zip"), reverse=True):
        items.append({"name": path.name, "path": str(path), "size": str(path.stat().st_size)})
    return items


def restore_backup(zip_path: Path) -> Path:
    source = Path(zip_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError("архив не найден")
    if not _is_inside(source, DATA_DIR):
        raise PermissionError("восстановление только из папки данных NOVA")
    create_backup(include_secrets=True)
    with zipfile.ZipFile(source, "r") as archive:
        _safe_extract(archive, DATA_DIR)
    migrate()
    return DATA_DIR
