import pytest

from jarvis.tools import ToolContext, execute_tool, tool_get_datetime


@pytest.mark.asyncio
async def test_datetime_moscow():
    ctx = ToolContext()
    text = await tool_get_datetime(ctx, timezone="Europe/Moscow")
    assert "Europe/Moscow" in text
    assert "datetime" in ctx.log


@pytest.mark.asyncio
async def test_unknown_tool():
    result = await execute_tool(ToolContext(), "launch_missiles", {})
    assert "Неизвестный" in result


@pytest.mark.asyncio
async def test_web_search_tool(monkeypatch):
    from jarvis import tools as toolsmod

    def fake_search(query, max_results=8, region="wt-wt"):
        return [{"title": "Результат", "url": "https://example.com", "snippet": query}]

    monkeypatch.setattr(toolsmod, "search_web", fake_search)
    result = await execute_tool(ToolContext(), "web_search", {"query": "курс евро"})
    assert "example.com" in result
    assert "курс евро" in result
