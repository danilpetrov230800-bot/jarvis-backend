from jarvis import config, secrets, storage


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DATABASE", tmp_path / "nova.db")
    monkeypatch.setattr(secrets, "DATA_DIR", tmp_path)
    monkeypatch.setattr(secrets, "SECRET_FILE", tmp_path / ".api-key")
    storage.initialize()


def test_management_api_end_to_end(client, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    memory = client.post("/api/memory", json={"content": "важный факт", "importance": 5})
    assert memory.status_code == 200
    assert client.get("/api/memory?q=важный").json()[0]["content"] == "важный факт"

    skill = client.post("/api/skills", json={"name": "Режим", "trigger": "режим", "actions": [{"type": "command", "value": "test"}]})
    assert skill.status_code == 200
    assert client.get("/api/skills").json()[0]["name"] == "Режим"

    agent = client.post("/api/agents", json={"name": "Research", "role": "public research"})
    assert agent.status_code == 200
    task = client.post("/api/tasks", json={"title": "Проверка", "task_type": "agent"})
    assert task.status_code == 200
    assert client.delete(f"/api/tasks/{task.json()['id']}").json() == {"deleted": True}


def test_permission_api_and_file_path_defense(client, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    denied = client.post("/api/tools/files", json={"operation": "find", "path": str(tmp_path)})
    assert denied.status_code == 403
    assert denied.json()["permission"] == "READ_FILES"
    assert client.put("/api/permissions/READ_FILES", json={"enabled": True}).status_code == 200
    outside = client.post("/api/tools/files", json={"operation": "find", "path": "/etc"})
    assert outside.status_code == 400


def test_diagnostics_backup_and_secret_redaction(client, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert client.post("/api/settings", json={"api_key": "not-for-logs"}).status_code == 200
    response = client.get("/api/settings").json()
    assert response["has_api_key"] is True
    assert "not-for-logs" not in str(response)
    assert client.get("/api/diagnostics").status_code == 200
    backup = client.post("/api/backup")
    assert backup.status_code == 200
    assert backup.json()["path"].endswith(".zip")


def test_unknown_file_operation_is_safe_error(client, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    response = client.post("/api/tools/files", json={"operation": "shell", "path": "."})
    assert response.status_code == 400
    assert "Неизвестная" in response.json()["detail"]


def test_stress_one_hundred_offline_messages(client, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    for _ in range(100):
        response = client.post("/api/chat", json={"text": "привет"})
        assert response.status_code == 200
        assert response.json()["provider"] == "local"
