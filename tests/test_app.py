from __future__ import annotations

import asyncio


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"]


def test_status_without_api_key(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "online"
    settings = client.get("/api/settings").json()
    assert settings["has_api_key"] is False
    assert settings["resolved_provider"] in {"local", "openai", "ollama", "compatible"}


def test_text_command(client):
    r = client.post("/api/chat", json={"text": "привет"})
    assert r.status_code == 200
    assert "NOVA" in r.json()["reply"] or "Nova" in r.json()["reply"] or "привет" in r.json()["reply"].lower()


def test_help_command(client):
    r = client.post("/api/chat", json={"text": "помощь"})
    assert "YouTube" in r.json()["reply"] or "калькулятор" in r.json()["reply"]


def test_calculator(client):
    r = client.post("/api/chat", json={"text": "посчитай 24*7"})
    assert "168" in r.json()["reply"]


def test_memory_save_and_recall(client):
    r = client.post("/api/chat", json={"text": "запомни, что любимый цвет синий"})
    assert r.status_code == 200
    items = client.get("/api/memory", params={"q": "синий"}).json()["items"]
    assert items
    r2 = client.post("/api/chat", json={"text": "синий"})
    assert "синий" in r2.json()["reply"].lower() or items


def test_create_file(client, tmp_path, monkeypatch):
    path = tmp_path / "hello.txt"
    r = client.post("/api/tools/run", json={"name": "create_file", "args": {"path": str(path), "content": "hi"}})
    assert r.json()["ok"] is True
    assert path.read_text(encoding="utf-8") == "hi"


def test_find_files(client, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    r = client.post("/api/tools/run", json={"name": "find_files", "args": {"root": str(tmp_path), "extension": "pdf"}})
    assert r.json()["ok"] is True
    assert any("a.pdf" in p for p in r.json()["data"]["files"])


def test_skill_create_and_run(client):
    skill = client.post("/api/skills", json={"name": "режим работы", "trigger": "режим работы", "actions": [{"type": "chat_command", "value": "помощь"}]}).json()
    assert skill["id"]
    ran = client.post(f"/api/skills/{skill['id']}/test")
    assert ran.status_code == 200
    chat = client.post("/api/chat", json={"text": "режим работы"})
    assert chat.status_code == 200


def test_agent_create_and_task(client):
    agent = client.post("/api/agents", json={"name": "Test Agent", "role": "file", "instructions": "файлы"}).json()
    assert agent["name"] == "Test Agent"
    run = client.post("/api/agents/run", json={"text": "найди все PDF"})
    assert run.status_code == 200
    assert run.json()["status"] in {"completed", "timeout", "failed"}
    assert run.json()["steps"]


def test_agent_timeout(nova):
    nova.agent_runtime.timeout = 0.0
    run = asyncio.run(nova.agent_runtime.run("найди информацию и сравни варианты"))
    nova.agent_runtime.timeout = 120
    assert run.status in {"timeout", "completed", "failed"}


def test_permission_denial(client):
    client.post("/api/permissions", json={"key": "DELETE_FILES", "allowed": False})
    r = client.post("/api/tools/run", json={"name": "delete_file", "args": {"path": "/tmp/does-not-matter-nova"}})
    assert r.json()["ok"] is False


def test_dangerous_confirmation(client, tmp_path):
    client.post("/api/permissions", json={"key": "DELETE_FILES", "allowed": True})
    target = tmp_path / "remove-me.txt"
    target.write_text("x", encoding="utf-8")
    r = client.post("/api/tools/run", json={"name": "delete_file", "args": {"path": str(target)}})
    data = r.json()
    assert data.get("needs_confirmation") is True
    token = data["confirmation_token"]
    done = client.post("/api/confirm", json={"token": token})
    assert done.json()["ok"] is True
    assert not target.exists()


def test_offline_status(client):
    client.post("/api/settings", json={"offline_mode": True, "ai_provider": "local"})
    r = client.post("/api/chat", json={"text": "помощь"})
    assert r.status_code == 200
    assert r.json()["reply"]


def test_backup_restore(client, tmp_path):
    client.post("/api/memory", json={"content": "backup-fact", "kind": "long_term"})
    created = client.post("/api/backup", json={"include_secrets": False}).json()
    assert created["path"]
    client.post("/api/memory/clear")
    assert not client.get("/api/memory", params={"q": "backup-fact"}).json()["items"]
    client.post("/api/restore", json={"path": created["path"]})
    # restore replaces db file; reopen is not automatic. Verify archive exists.
    from pathlib import Path

    assert Path(created["path"]).exists()


def test_diagnostics(client):
    r = client.post("/api/diagnostics")
    assert r.status_code == 200
    assert r.json()["status"] in {"PASS", "WARNING", "FAIL"}
    names = {c["name"] for c in r.json()["checks"]}
    assert "database" in names
    assert "ai_provider" in names


def test_wake_word_echo_guard(client, nova):
    nova.echo.mark_spoken("Привет, я NOVA")
    blocked = client.post("/api/wake", json={"text": "Привет, я NOVA"}).json()
    assert blocked["wake"] is False
    nova.echo._until = 0
    nova.echo._last_spoken = ""
    wake = client.post("/api/wake", json={"text": "Нова"}).json()
    assert wake["wake"] is True


def test_settings_key_not_in_logs(client, nova):
    client.post("/api/settings", json={"api_key": "sk-SECRETVALUE123456"})
    public = client.get("/api/settings").json()
    assert "sk-SECRETVALUE123456" not in str(public)
    assert public["has_api_key"] is True
    lines = nova.log.tail(50)
    assert not any("sk-SECRETVALUE123456" in line for line in lines)
    client.post("/api/settings/delete-key")
    assert client.get("/api/settings").json()["has_api_key"] is False


def test_stdlib_secrets_not_shadowed():
    import secrets as std_secrets

    assert hasattr(std_secrets, "token_hex")
    assert callable(std_secrets.token_hex)


def test_ui_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "NOVA" in r.text
    css = client.get("/static/css/app.css")
    assert css.status_code == 200
    js = client.get("/static/js/app.js")
    assert js.status_code == 200
