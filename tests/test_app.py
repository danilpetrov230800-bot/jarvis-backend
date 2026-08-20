def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_and_home(client):
    status = client.get("/api/status")
    assert status.status_code == 200
    assert "NOVA" in status.json()["status"]
    assert status.json()["ready"] is True
    home = client.get("/")
    assert home.status_code == 200
    assert "text/html" in home.headers["content-type"]
    assert "NOVA" in home.text


def test_legacy_chat_without_key(client):
    response = client.post("/chat", json={"text": "привет"})
    assert response.status_code == 200
    body = response.json()
    assert "Nova" in body["reply"]
    assert body.get("speech")


def test_open_site_command(client, monkeypatch):
    monkeypatch.setattr("jarvis.desktop.open_url", lambda url: url)
    response = client.post("/api/chat", json={"text": "открой youtube"})
    assert response.status_code == 200
    body = response.json()
    assert "open_url" in body["tools"]


def test_pc_endpoints(client, monkeypatch):
    listing = client.get("/api/pc")
    assert listing.status_code == 200
    assert "volume_up" in listing.json()["actions"]
    monkeypatch.setattr("jarvis.pc_control.volume_up", lambda: "Громкость выше.")
    ok = client.post("/api/pc", json={"action": "volume_up"})
    assert ok.status_code == 200
    assert ok.json()["action"] == "volume_up"
    missing = client.post("/api/pc", json={"action": "explode"})
    assert missing.status_code == 400


def test_diagnostics_and_memory(client):
    diag = client.get("/api/diagnostics")
    assert diag.status_code == 200
    assert diag.json()["result"] in {"PASS", "WARNING", "FAIL"}
    added = client.post("/api/memory-long", json={"content": "тест памяти"})
    assert added.status_code == 200
    listed = client.get("/api/memory-long")
    assert any("тест памяти" in (row.get("content") or "") for row in listed.json()["items"])
