import pytest

from jarvis.config import Settings
from jarvis.llm import LLMError, chat_once
from jarvis.voice import prepare_speech_text


def test_prepare_speech_strips_markdown_and_urls():
    text = "Сэр, **готово**. Смотрите [сайт](https://example.com/page) и https://evil.test/x"
    cleaned = prepare_speech_text(text)
    assert "готово" in cleaned
    assert "**" not in cleaned
    assert "https://" not in cleaned
    assert "сайт" in cleaned


def test_build_client_requires_key():
    from jarvis.llm import build_client

    with pytest.raises(LLMError):
        build_client(Settings(provider="openai", api_key=""))


@pytest.mark.asyncio
async def test_chat_once_with_mocked_model(monkeypatch):
    class FakeFunction:
        name = "web_search"
        arguments = '{"query": "погода в Москве"}'

    class FakeCall:
        id = "call_1"
        function = FakeFunction()

    class Msg:
        def __init__(self, content, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls

    class Choice:
        def __init__(self, message):
            self.message = message

    class Resp:
        def __init__(self, message):
            self.choices = [Choice(message)]

    calls = {"n": 0}

    async def fake_complete(_client, _model, _messages, tools):
        calls["n"] += 1
        if calls["n"] == 1:
            return Resp(Msg("", [FakeCall()]))
        return Resp(Msg("Сэр, в Москве сейчас ясно, около пяти градусов."))

    async def fake_tool(_ctx, name, _arguments):
        assert name == "web_search"
        return "Москва, +5"

    monkeypatch.setattr("jarvis.llm._complete", fake_complete)
    monkeypatch.setattr("jarvis.llm.execute_tool", fake_tool)
    monkeypatch.setattr("jarvis.llm.build_client", lambda _s: object())

    result = await chat_once(Settings(api_key="x", provider="openai", model="test"), [], "Какая погода в Москве?")
    assert "Москве" in result["reply"]
    assert result["model"] == "test"
