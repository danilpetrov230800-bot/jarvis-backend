from pathlib import Path

import pytest

from nova_core.security import Permission
from nova_core.services import NovaServices
from nova_core.storage import Database, export_profile, restore_profile


@pytest.fixture
def services(tmp_path: Path) -> NovaServices:
    return NovaServices(Database(tmp_path / "nova.sqlite3"))


def test_memory_is_searchable_and_deletable(services: NovaServices):
    created = services.add_memory("Пользователь предпочитает русский язык", "preference", 4)
    assert services.memories("русский")[0]["id"] == created["id"]
    services.delete_memory(created["id"])
    assert services.memories() == []


def test_skills_reject_unsafe_actions(services: NovaServices):
    with pytest.raises(ValueError):
        services.create_skill("unsafe", "go", [{"type": "shell"}])

    skill = services.create_skill("Работа", "режим работы", [{"type": "wait", "seconds": 1}])
    assert services.skills()[0]["name"] == skill["name"]


def test_permissions_default_to_safe_and_can_change(services: NovaServices):
    assert services.permissions.allowed(Permission.READ_FILES)
    assert not services.permissions.allowed(Permission.DELETE_FILES)
    services.permissions.set(Permission.DELETE_FILES, True)
    assert services.permissions.allowed(Permission.DELETE_FILES)


def test_profile_export_and_restore(tmp_path: Path, services: NovaServices):
    services.add_memory("backup me")
    archive = export_profile(tmp_path / "profile.zip")
    assert archive.is_file()
    restore_profile(archive)
