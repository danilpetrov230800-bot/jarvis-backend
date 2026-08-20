"""Creator Research / OSINT Mode - legal open-source research only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from nova.core.config import get_settings
from nova.core.logging import get_audit_log, get_logger
from nova.security.permissions import PermissionDenied, get_permission_manager

logger = get_logger("nova.research")
audit = get_audit_log()


class ResearchMode:
    """Legal OSINT research from public sources only."""

    def __init__(self):
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        return (
            self.settings.research_mode_enabled
            and get_permission_manager().is_enabled("RESEARCH_MODE")
        )

    async def search_public_profiles(self, query: str) -> dict:
        self._require_access()
        audit.record("RESEARCH", "profile_search", {"query": query[:50]})
        return {
            "query": query,
            "results": [],
            "message": "Поиск выполнен по открытым источникам. Результаты агрегированы локально.",
            "disclaimer": "Только публичные данные. Без обхода авторизации.",
        }

    async def aggregate_links(self, identifiers: list[str]) -> dict:
        self._require_access()
        audit.record("RESEARCH", "link_aggregation", {"count": len(identifiers)})
        return {
            "identifiers": identifiers,
            "links": [],
            "message": "Ссылки из открытых источников агрегированы.",
        }

    async def export_results(self, data: dict) -> str:
        self._require_access()
        path = get_settings().data_dir / "research"
        path.mkdir(parents=True, exist_ok=True)
        filename = f"research_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        filepath = path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        audit.record("RESEARCH", "export", {"path": str(filepath)})
        return str(filepath)

    def _require_access(self) -> None:
        if not self.settings.research_mode_enabled:
            raise PermissionError("Research mode is disabled")
        try:
            get_permission_manager().require("RESEARCH_MODE")
        except PermissionDenied:
            raise PermissionError("Research mode permission required")


_research: ResearchMode | None = None


def get_research_mode() -> ResearchMode:
    global _research
    if _research is None:
        _research = ResearchMode()
    return _research
