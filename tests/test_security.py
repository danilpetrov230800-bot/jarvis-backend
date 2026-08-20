def test_calculator_rejects_code(client):
    r = client.post("/api/tools/run", json={"name": "calculator", "args": {"expr": "__import__('os').system('id')"}})
    assert r.json()["ok"] is False


def test_zip_slip_rejected(client, tmp_path):
    import zipfile

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    r = client.post("/api/tools/run", json={"name": "extract_archive", "args": {"path": str(evil), "destination": str(tmp_path / "out")}})
    assert r.json()["ok"] is False


def test_malformed_chat(client):
    r = client.post("/api/chat", json={"text": ""})
    assert r.status_code == 422


def test_invalid_tool_name(client):
    r = client.post("/api/tools/run", json={"name": "not_a_tool", "args": {}})
    assert r.json()["ok"] is False


def test_confirm_invalid_token(client):
    r = client.post("/api/confirm", json={"token": "nope"})
    assert r.status_code in {400, 403} or r.json().get("ok") is False or r.status_code == 400


def test_research_requires_permission(client):
    client.post("/api/settings", json={"research_enabled": True})
    client.post("/api/permissions", json={"key": "RESEARCH", "allowed": False})
    r = client.post("/api/research", json={"identifier": "octocat"})
    assert r.status_code in {400, 403}
