from __future__ import annotations

from nova import __version__


class UpdateService:
    def current(self) -> dict[str, str]:
        return {
            "version": __version__,
            "channel": "stable",
            "status": "up-to-date",
            "note": "Перед обновлением NOVA автоматически создаёт резервную копию профиля.",
        }
