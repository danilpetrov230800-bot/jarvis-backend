from jarvis.search import search_web


class FakeDDGS:
    last_kwargs = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def text(self, query, **kwargs):
        FakeDDGS.last_kwargs = {"query": query, **kwargs}
        return [
            {"title": "A", "href": "https://example.com/a", "body": "one"},
            {"title": "track", "href": "https://googleadservices.com/x", "body": "ads"},
            {"title": "A copy", "href": "https://example.com/a", "body": "dup"},
            {"title": "B", "href": "https://example.com/b", "body": "two"},
        ]


def test_search_uses_safesearch_off(monkeypatch):
    monkeypatch.setattr("jarvis.search._ddgs", lambda: FakeDDGS())
    results = search_web("что угодно", max_results=5)
    assert FakeDDGS.last_kwargs["safesearch"] == "off"
    assert FakeDDGS.last_kwargs["query"] == "что угодно"
    urls = [item["url"] for item in results]
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_search_blank_query(monkeypatch):
    monkeypatch.setattr("jarvis.search._ddgs", lambda: FakeDDGS())
    assert search_web("   ") == []
