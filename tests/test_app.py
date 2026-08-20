from jarvis.config import Settings
from jarvis.llm import LLMError


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_and_home(client):
    status = client.get("/api/status")
    assert status.status_code == 200
    assert "JARVIS" in status.json()["status"]
    home = client.get("/")
    assert home.status_code == 200
    assert "text/html" in home.headers["content-type"]
    assert "JARVIS" in home.text


def test_legacy_chat_without_key(client, monkeypatch):
    from jarvis import app as appmod

    monkeypatch.setattr(appmod, "load_settings", lambda: Settings(api_key="", provider="openai"))

    async def boom(*_args, **_kwargs):
        raise LLMError("Не задан API-ключ")

    monkeypatch.setattr(appmod, "chat_once", boom)
    response = client.post("/chat", json={"text": "привет"})
    assert response.status_code == 400
    assert "ключ" in response.json()["detail"].lower()
