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
    result = await respond(Settings(api_key=""), [], "найди python")
    assert "Пример" in result["reply"] or "python" in result["reply"].lower()
    assert result["sources"]


@pytest.mark.asyncio
async def test_wiki_intent(monkeypatch):
    async def fake_wiki(topic):
        return {"reply": f"Статья про {topic}", "title": topic, "url": "https://ru.wikipedia.org"}

    monkeypatch.setattr("jarvis.services.wiki_summary", fake_wiki)
    result = await respond(Settings(api_key=""), [], "что такое квантовый компьютер")
    assert "квантов" in result["reply"].lower()
    assert "wiki" in result["tools"]


@pytest.mark.asyncio
async def test_volume_command(monkeypatch):
    monkeypatch.setattr("jarvis.pc_control.require", lambda permission: None)
    monkeypatch.setattr("jarvis.pc_control._key", lambda *args, **kwargs: None)
    result = await respond(Settings(api_key=""), [], "громче")
    assert "volume" in result["tools"]


@pytest.mark.asyncio
async def test_greeting_with_punctuation():
    result = await respond(Settings(api_key=""), [], "привет!")
    assert "Nova" in result["reply"]


@pytest.mark.asyncio
async def test_eurovision_is_not_currency(monkeypatch):
    monkeypatch.setattr(
        "jarvis.brain.search_web",
        lambda query, region="ru-ru": [{"title": "Евровидение", "url": "https://example.com", "snippet": "конкурс"}],
    )
    result = await respond(Settings(api_key=""), [], "найди евровидение")
    assert "currency" not in result["tools"]
    assert "web_search" in result["tools"]


@pytest.mark.asyncio
async def test_translate_to_english(monkeypatch):
    async def fake_translate(phrase, target="ru"):
        assert target == "en"
        return {"reply": "hello", "title": "Перевод", "url": "https://translate.google.com"}

    monkeypatch.setattr("jarvis.services.translate_text", fake_translate)
    result = await respond(Settings(api_key=""), [], "переведи привет на английский")
    assert result["reply"] == "hello"
    assert "translate" in result["tools"]


def test_summarize_search_empty():
    assert "ничего не нашла" in summarize_search("zzz", [])
