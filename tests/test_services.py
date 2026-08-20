import pytest

from jarvis import services


class FakeResp:
    def __init__(self, payload, text=""):
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_weather(monkeypatch):
    async def fake_geocode(city):
        return {"name": city, "lat": 55.7, "lon": 37.6, "country": "RU"}

    monkeypatch.setattr(services, "geocode", fake_geocode)
    monkeypatch.setattr(
        services.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(
            FakeResp(
                {
                    "current": {
                        "temperature_2m": 5,
                        "apparent_temperature": 3,
                        "relative_humidity_2m": 70,
                        "wind_speed_10m": 2,
                        "weather_code": 0,
                    }
                }
            )
        ),
    )
    data = await services.get_weather("Москва")
    assert "Москва" in data["reply"]
    assert "5" in data["reply"]


@pytest.mark.asyncio
async def test_traffic(monkeypatch):
    monkeypatch.setattr(
        services,
        "search_web",
        lambda query, max_results=5, region="ru-ru": [
            {"title": "Пробки", "url": "https://example.com", "snippet": "2 балла"}
        ],
    )
    data = await services.get_traffic("Москва")
    assert "Пробки" in data["reply"]
    assert "yandex.ru/maps" in str(data["maps"])


@pytest.mark.asyncio
async def test_currency(monkeypatch):
    monkeypatch.setattr(
        services.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(
            FakeResp(
                {
                    "Date": "2026-08-20T00:00:00",
                    "Valute": {
                        "USD": {"Value": 90.12},
                        "EUR": {"Value": 98.4},
                        "CNY": {"Value": 12.3},
                    },
                }
            )
        ),
    )
    data = await services.get_currency()
    assert "90.12" in data["reply"]
    assert "ЦБ" in data["title"]
