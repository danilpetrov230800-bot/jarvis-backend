"""Backup and restore for NOVA."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from nova.agents.manager import get_agent_manager
from nova.core.config import get_settings
from nova.core.logging import get_logger
from nova.memory.store import get_memory_store
from nova.skills.manager import get_skill_manager

logger = get_logger("nova.backup")


class BackupManager:
    def __init__(self):
        self.settings = get_settings()

    def create_backup(self, include_secrets: bool = False) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = self.settings.backups_dir / f"nova_backup_{ts}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.settings.version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "settings": {},
            "memory": get_memory_store().export_all(),
            "skills": get_skill_manager().list_all(),
            "agents": get_agent_manager().list_all(),
        }

        with open(backup_dir / "profile.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if self.settings.db_path.exists():
            shutil.copy2(self.settings.db_path, backup_dir / "nova.db")

        archive = self.settings.backups_dir / f"nova_backup_{ts}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in backup_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(backup_dir))

        shutil.rmtree(backup_dir)
        logger.info("Backup created: %s", archive)
        return str(archive)

    def restore_backup(self, archive_path: str) -> dict:
        path = Path(archive_path)
        if not path.exists():
            return {"error": "Backup file not found"}

        extract_dir = self.settings.backups_dir / "restore_temp"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)

        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(extract_dir)

        profile_path = extract_dir / "profile.json"
        if not profile_path.exists():
            return {"error": "Invalid backup: profile.json missing"}

        with open(profile_path, encoding="utf-8") as f:
            data = json.load(f)

        memory = get_memory_store()
        memory.clear()
        memory.import_records(data.get("memory", []))

        db_backup = extract_dir / "nova.db"
        if db_backup.exists():
            shutil.copy2(db_backup, self.settings.db_path)

        shutil.rmtree(extract_dir)
        logger.info("Backup restored from: %s", archive_path)
        return {"restored": True, "version": data.get("version")}

    def list_backups(self) -> list[str]:
        return sorted((str(p) for p in self.settings.backups_dir.glob("nova_backup_*.zip")), reverse=True)


_manager: BackupManager | None = None


def get_backup_manager() -> BackupManager:
    global _manager
    if _manager is None:
        _manager = BackupManager()
    return _manager
