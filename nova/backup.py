from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from nova.db import Database
from nova.paths import backup_dir, data_dir, db_path, settings_path
from nova.secretstore import SecretStore
from nova.settings import SettingsService


class BackupService:
    def __init__(self, db: Database, settings: SettingsService, secrets: SecretStore) -> None:
        self.db = db
        self.settings = settings
        self.secrets = secrets

    def create(self, include_secrets: bool = False, label: str = "manual") -> Path:
        dest = backup_dir() / f"nova-profile-{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if db_path().exists():
                zf.write(db_path(), arcname="nova.db")
            if settings_path().exists():
                zf.write(settings_path(), arcname="settings.json")
            payload: dict[str, Any] = {
                "settings": self.settings.public(),
                "include_secrets": include_secrets,
            }
            if include_secrets:
                payload["secrets"] = self.secrets.export_plain()
            zf.writestr("manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))
        return dest

    def restore(self, archive: Path, include_secrets: bool = False) -> None:
        with zipfile.ZipFile(archive, "r") as zf:
            names = zf.namelist()
            if "nova.db" in names:
                target = db_path()
                target.write_bytes(zf.read("nova.db"))
            if "settings.json" in names:
                settings_path().write_bytes(zf.read("settings.json"))
            if include_secrets and "manifest.json" in names:
                manifest = json.loads(zf.read("manifest.json"))
                for key, value in (manifest.get("secrets") or {}).items():
                    self.secrets.set(key, value)
        self.settings.load()

    def list(self) -> list[dict[str, str]]:
        items = []
        for path in sorted(backup_dir().glob("*.zip"), reverse=True):
            items.append({"name": path.name, "path": str(path), "size": str(path.stat().st_size)})
        return items
