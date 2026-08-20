import asyncio
import io
import zipfile
from pathlib import Path

import pytest

from jarvis.agent import run_agent
from jarvis.agents_catalog import create_agent, list_agents, seed_agents
from jarvis.backup import create_backup, restore_backup
from jarvis.files_agent import create_file, delete_file
from jarvis.logs import redact
from jarvis.permissions import allowed, save
from jarvis.skills import create_skill, match_skill
from jarvis.store import migrate


def test_text_command_without_key(client):
    response = client.post("/api/chat", json={"text": "привет"})
    assert response.status_code == 200
    assert "Nova" in response.json()["reply"]


def test_open_app_command(client, monkeypatch):
    monkeypatch.setattr("jarvis.desktop.open_app", lambda name: "notepad")
    response = client.post("/api/chat", json={"text": "открой блокнот"})
    assert response.status_code == 200
    assert response.json()["tools"]


def test_file_create_and_confirm_delete(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.files_agent.user_roots", lambda: [tmp_path])
    monkeypatch.setattr("jarvis.files_agent.DATA_DIR", tmp_path)
    monkeypatch.setattr("jarvis.files_agent.Path.home", lambda: tmp_path)
    monkeypatch.setattr("jarvis.permissions.PATH", tmp_path / "permissions.json")
    monkeypatch.setattr("jarvis.permissions.DATA_DIR", tmp_path)
    save({"DELETE_FILES": True, "WRITE_FILES": True, "READ_FILES": True})
    (tmp_path / "Documents").mkdir()
    created = create_file("hello.txt", "hi")
    assert created.exists()
    msg = delete_file(str(created), confirm=False)
    assert "подтвержд" in msg.lower() or "confirm" in msg.lower()
    assert created.exists()
    delete_file(str(created), confirm=True)
    assert not created.exists()


def test_skill_create_and_run(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    monkeypatch.setattr("jarvis.skills.open_url", lambda url: url)
    monkeypatch.setattr("jarvis.skills.open_app", lambda name: name)
    create_skill("work", "режим работы", action_text="открой chrome")
    result = match_skill("режим работы")
    assert result is not None
    assert "skill" in result.tools


def test_agent_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    seed_agents()
    names = {item["name"] for item in list_agents()}
    assert "Research" in names
    custom = create_agent("MyBot", role="research", instructions="ищи")
    assert custom["name"] == "MyBot"


@pytest.mark.asyncio
async def test_agent_timeout(monkeypatch):
    async def slow(*_args, **_kwargs):
        await asyncio.sleep(2)
        return {"reply": "late", "tools": ["agent"], "sources": [], "steps": []}

    monkeypatch.setattr("jarvis.agent._run", slow)
    result = await run_agent("найди python", timeout=0.05)
    assert "остановлен" in result["reply"].lower() or "таймаут" in result["reply"].lower()


@pytest.mark.asyncio
async def test_agent_retry(monkeypatch):
    calls = {"n": 0}

    def boom(*_args, **_kwargs):
        calls["n"] += 1
        raise RuntimeError("net down")

    monkeypatch.setattr("jarvis.agent.search_web", boom)

    async def fake_wiki(_topic):
        return {"reply": "wiki", "title": "t", "url": "https://example.com"}

    monkeypatch.setattr("jarvis.agent.wiki_summary", fake_wiki)
    result = await run_agent("найди python", retry_limit=2, timeout=8)
    assert calls["n"] == 3
    assert "agent" in result["tools"]


def test_permission_denial(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.permissions.PATH", tmp_path / "permissions.json")
    monkeypatch.setattr("jarvis.permissions.DATA_DIR", tmp_path)
    save({"READ_FILES": False})
    assert allowed("READ_FILES") is False


def test_research_requires_permission(client, tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.permissions.PATH", tmp_path / "permissions.json")
    monkeypatch.setattr("jarvis.permissions.DATA_DIR", tmp_path)
    save({"RESEARCH": False})
    response = client.post("/api/research", json={"query": "публичный профиль"})
    assert response.status_code == 403


def test_backup_and_restore(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.backup.DATA_DIR", tmp_path)
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    archive = create_backup(include_secrets=False)
    assert archive.exists()
    (tmp_path / "notes.txt").write_text("changed", encoding="utf-8")
    restore_backup(archive)
    assert "hello" in (tmp_path / "notes.txt").read_text(encoding="utf-8")


def test_restore_rejects_outside_path(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.backup.DATA_DIR", tmp_path)
    outside = tmp_path.parent / "evil.zip"
    outside.write_bytes(b"PK")
    with pytest.raises(PermissionError):
        restore_backup(outside)


def test_zip_slip_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.backup.DATA_DIR", tmp_path)
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    evil = tmp_path / "backups"
    evil.mkdir(parents=True, exist_ok=True)
    archive = evil / "nova-backup-slip.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "nope")
    archive.write_bytes(buf.getvalue())
    with pytest.raises(ValueError):
        restore_backup(archive)


def test_secret_not_in_redacted_logs():
    assert "gsk_live_secret_key_value" not in redact("token=gsk_live_secret_key_value")
    assert "[redacted]" in redact("api_key=sk-abcdefghijklmnopqrstuvwxyz")


def test_malformed_chat(client):
    empty = client.post("/api/chat", json={"text": ""})
    assert empty.status_code == 422
    huge = client.post("/api/chat", json={"text": "x" * 9000})
    assert huge.status_code == 422


def test_command_injection_filename(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.files_agent.user_roots", lambda: [tmp_path])
    monkeypatch.setattr("jarvis.files_agent.DATA_DIR", tmp_path)
    monkeypatch.setattr("jarvis.files_agent.Path.home", lambda: tmp_path)
    (tmp_path / "Documents").mkdir()
    path = create_file("evil;rm.txt", "safe")
    assert path.parent == tmp_path / "Documents"
    assert ";" in path.name or path.name.startswith("x")
    assert path.read_text(encoding="utf-8") == "safe"


def test_offline_status(client, monkeypatch):
    monkeypatch.setattr("jarvis.app.is_offline", lambda force=False: True)
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["offline"] is True


def test_diagnostics_and_agents_ui(client):
    diag = client.get("/api/diagnostics")
    assert diag.status_code == 200
    names = {row["name"] for row in diag.json()["checks"]}
    assert "database" in names
    assert "permissions" in names
    agents = client.get("/api/agents")
    assert agents.status_code == 200
    assert agents.json()["items"]
    home = client.get("/").text
    assert 'data-page="agents"' in home
    assert "confirmDlg" in home
    assert "wizMic" in home


def test_updates_and_export_logs(client):
    updates = client.get("/api/updates")
    assert updates.status_code == 200
    assert "1.5.0" in updates.json()["current"]
    exported = client.get("/api/logs/export")
    assert exported.status_code == 200


def test_stress_many_messages(client):
    for i in range(40):
        response = client.post("/api/chat", json={"text": "привет"})
        assert response.status_code == 200
        assert response.json()["reply"]
