import json
import time
import zipfile
from pathlib import Path

import pytest

from jarvis import agents, config, core, permissions, secrets, storage
from jarvis.config import Settings
from jarvis.skills import execute_skill, matching_skill


@pytest.fixture()
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DATABASE", tmp_path / "nova.db")
    monkeypatch.setattr(secrets, "DATA_DIR", tmp_path)
    monkeypatch.setattr(secrets, "SECRET_FILE", tmp_path / ".api-key")
    storage.initialize()
    return tmp_path


def test_memory_skill_agent_task_crud(isolated_data):
    memory = core.save_memory("Пользователь любит краткие ответы", "preference", "communication", 5)
    assert memory["kind"] == "preference"
    assert core.search_memory("краткие")[0]["id"] == memory["id"]

    skill = core.save_skill({"name": "Рабочий режим", "trigger": "работа", "actions": [{"type": "command", "value": "open"}]})
    assert skill["version"] == 1
    assert skill["actions"][0]["type"] == "command"

    agent = core.save_agent({"name": "File Agent", "role": "files", "tools": ["find"], "permissions": ["READ_FILES"]})
    assert agent["tools"] == ["find"]

    task = core.save_task({"title": "Напомнить", "task_type": "reminder", "schedule": "18:00"})
    assert task["status"] == "pending"
    assert core.delete_record("tasks", task["id"])


def test_skill_update_increments_version(isolated_data):
    data = {"name": "Test Skill", "trigger": "one", "actions": [{"type": "command", "value": "x"}]}
    assert core.save_skill(data)["version"] == 1
    data["trigger"] = "two"
    assert core.save_skill(data)["version"] == 2


def test_permissions_are_deny_by_default(isolated_data):
    permissions.initialize_permissions()
    with pytest.raises(permissions.PermissionDenied):
        permissions.require("DELETE_FILES")
    permissions.set_permission("READ_FILES", True)
    permissions.require("READ_FILES")
    assert next(item for item in permissions.list_permissions() if item["name"] == "READ_FILES")["enabled"]


def test_backup_restore_and_traversal_rejection(isolated_data):
    core.save_memory("backup me")
    archive = storage.create_backup()
    assert archive.is_file()

    malicious = isolated_data / "bad.zip"
    with zipfile.ZipFile(malicious, "w") as output:
        output.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="Небезопасный"):
        storage.restore_backup(malicious)


def test_api_key_not_written_to_settings(isolated_data):
    settings = config.Settings(api_key="super-secret")
    config.save_settings(settings)
    assert "super-secret" not in config.SETTINGS_PATH.read_text("utf-8")
    assert config.load_settings().api_key == "super-secret"


def test_bounded_execution_timeout_and_retry(isolated_data):
    attempts = 0

    def flaky():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("retry")
        return "ok"

    assert core.run_bounded(flaky, timeout=1, retry_limit=1) == "ok"
    with pytest.raises(TimeoutError):
        core.run_bounded(lambda: time.sleep(0.25), timeout=0.1, retry_limit=0)


def test_malformed_records_rejected(isolated_data):
    with pytest.raises(ValueError):
        core.save_memory("", "long_term")
    with pytest.raises(ValueError):
        core.save_skill({"name": "../bad", "trigger": "x", "actions": ["x"]})
    with pytest.raises(ValueError):
        core.save_task({"title": "x", "task_type": "infinite"})


def test_stress_one_hundred_memory_records(isolated_data):
    for index in range(120):
        core.save_memory(f"record {index}", importance=index % 5 + 1)
    assert len(core.list_records("memories")) == 120


def test_skill_matches_and_executes_local_action(isolated_data, monkeypatch):
    core.save_skill({"name": "Время", "trigger": "режим теста", "actions": [{"type": "command", "value": "который час"}]})
    skill = matching_skill("режим теста")
    assert skill is not None
    result = execute_skill(skill)
    assert "datetime" in result.tools


@pytest.mark.asyncio
async def test_agent_plans_retries_verifies_and_completes(isolated_data):
    calls = 0

    async def execute(step):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return {"reply": f"done: {step}", "tools": ["test"]}

    result = await agents.run_agent(
        {"name": "Testing Agent", "enabled": True},
        "первый шаг; второй шаг",
        Settings(),
        execute,
        max_steps=3,
        timeout=2,
        retry_limit=1,
    )
    assert result["completed"] is True
    assert any(event["status"] == "retry" for event in result["events"])
    assert len([event for event in result["events"] if event["status"] == "verified"]) == 2
