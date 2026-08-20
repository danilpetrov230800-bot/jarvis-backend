import pytest

from jarvis.brain import respond, summarize_search
from jarvis.config import Settings


@pytest.mark.asyncio
async def test_greeting_without_api_key():
    result = await respond(Settings(api_key=""), [], "привет")
    assert "Nova" in result["reply"]
    assert result["provider"] == "local"


@pytest.mark.asyncio
async def test_open_command_without_api_key(monkeypatch):
    monkeypatch.setattr("jarvis.desktop.open_url", lambda url: url)
    result = await respond(Settings(api_key=""), [], "открой youtube")
    assert "open_url" in result["tools"]


@pytest.mark.asyncio
async def test_search_fallback(monkeypatch):
    monkeypatch.setattr(
        "jarvis.brain.search_web",
        lambda query, region="wt-wt": [{"title": "Пример", "url": "https://example.com", "snippet": "текст"}],
    )
    result = await respond(Settings(api_key=""), [], "что такое квантовый компьютер")
    assert "квантов" in result["reply"].lower() or "Пример" in result["reply"]
    assert result["sources"]


def test_summarize_search_empty():
    assert "ничего не нашла" in summarize_search("zzz", [])
