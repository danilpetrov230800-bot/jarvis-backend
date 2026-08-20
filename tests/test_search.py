from jarvis.search import format_search_results, html_to_text, serialize_sources


def test_html_to_text_strips_noise():
    html = """
    <html><head><title>Новость</title><script>secret()</script></head>
    <body>
      <nav>меню</nav>
      <h1>Заголовок</h1>
      <p>Текст статьи про погоду в Москве.</p>
    </body></html>
    """
    text = html_to_text(html)
    assert "Заголовок" in text
    assert "погоду" in text
    assert "secret" not in text
    assert "меню" not in text


def test_format_and_serialize_results():
    results = [
        {"title": "Пример", "url": "https://example.com", "snippet": "описание"},
        {"title": "", "url": "https://example.org", "snippet": "ещё"},
    ]
    blob = format_search_results(results)
    assert "example.com" in blob
    assert "Без названия" in blob
    assert serialize_sources(results)[0]["url"] == "https://example.com"


def test_empty_search_message():
    assert "не дал" in format_search_results([]).lower()
