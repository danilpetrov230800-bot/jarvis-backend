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
    assert "Nova" in response.json()["reply"]


def test_open_site_command(client, monkeypatch):
    monkeypatch.setattr("jarvis.desktop.open_url", lambda url: url)
    response = client.post("/api/chat", json={"text": "открой youtube"})
    assert response.status_code == 200
    body = response.json()
    assert "open_url" in body["tools"]
