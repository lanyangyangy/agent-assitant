from __future__ import annotations

from datetime import UTC, datetime
import importlib
from typing import Any

import httpx
import pytest


class FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class FakeHttpClient:
    def __init__(
        self,
        post_payloads: list[dict[str, Any]] | None = None,
        get_payloads: list[dict[str, Any]] | None = None,
    ):
        self.post_payloads = list(post_payloads or [])
        self.get_payloads = list(get_payloads or [])
        self.post_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        return FakeResponse(self.post_payloads.pop(0))

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_calls.append({"url": url, **kwargs})
        return FakeResponse(self.get_payloads.pop(0))

    async def aclose(self) -> None:
        self.closed = True


class FailingPostClient:
    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        raise httpx.RequestError("network down")

    async def aclose(self) -> None:
        return None


class FailingGetClient:
    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        raise httpx.RequestError("network down")

    async def aclose(self) -> None:
        return None


def _search_module():
    return importlib.import_module("src.tools.search")


def _weather_module():
    return importlib.import_module("src.tools.weather")


def _time_module():
    return importlib.import_module("src.tools.time_tool")


def _registry_module():
    return importlib.import_module("src.tools.registry")


@pytest.mark.asyncio
async def test_tavily_search_posts_expected_request_and_returns_answer_results():
    client = FakeHttpClient(
        post_payloads=[
            {
                "answer": "Qwen 可以调用工具。",
                "results": [
                    {
                        "title": "Qwen tool use",
                        "url": "https://example.test/qwen",
                        "content": "工具调用说明",
                        "score": 0.9,
                    }
                ],
            }
        ]
    )
    tool = _search_module().TavilySearchTool(api_key="tavily-key", http_client=client)

    result = await tool.run({"query": "Qwen tools", "max_results": 2})

    assert client.post_calls == [
        {
            "url": "https://api.tavily.com/search",
            "headers": {"Authorization": "Bearer tavily-key"},
            "json": {
                "query": "Qwen tools",
                "search_depth": "basic",
                "max_results": 2,
                "include_answer": True,
            },
        }
    ]
    assert result == {
        "answer": "Qwen 可以调用工具。",
        "results": [
            {
                "title": "Qwen tool use",
                "url": "https://example.test/qwen",
                "content": "工具调用说明",
            }
        ],
    }


def test_tavily_search_requires_api_key_with_chinese_message():
    with pytest.raises(ValueError) as exc_info:
        _search_module().TavilySearchTool(api_key=None)

    assert "Tavily API Key" in str(exc_info.value)
    assert "缺少" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tavily_search_default_max_results_and_does_not_close_injected_client():
    client = FakeHttpClient(post_payloads=[{"answer": None, "results": []}])
    tool = _search_module().TavilySearchTool(api_key="tavily-key", http_client=client)

    assert [(p.name, p.required, p.default) for p in tool.parameters] == [
        ("query", True, None),
        ("max_results", False, 5),
    ]

    await tool.run({"query": "default max"})
    await tool.aclose()

    assert client.post_calls[0]["json"]["max_results"] == 5
    assert client.closed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("max_results", [True, 0, 11])
async def test_tavily_search_rejects_invalid_max_results(max_results: Any):
    client = FakeHttpClient(post_payloads=[{"answer": None, "results": []}])
    tool = _search_module().TavilySearchTool(api_key="tavily-key", http_client=client)

    with pytest.raises(ValueError) as exc_info:
        await tool.run({"query": "bad max", "max_results": max_results})

    assert "max_results" in str(exc_info.value)
    assert "1-10" in str(exc_info.value)
    assert client.post_calls == []


@pytest.mark.asyncio
async def test_tavily_search_request_error_returns_stable_chinese_registry_message():
    errors = importlib.import_module("src.tools.errors")
    registry = _registry_module().ToolRegistry()
    registry.register(
        _search_module().TavilySearchTool(api_key="tavily-key", http_client=FailingPostClient())
    )

    result = await registry.invoke("search", {"query": "network"})

    assert result.success is False
    assert result.error_code == errors.ToolErrorCode.EXECUTION_ERROR
    assert "Tavily 搜索请求失败" in result.message


@pytest.mark.asyncio
async def test_tavily_search_closes_self_created_client(monkeypatch):
    client = FakeHttpClient(post_payloads=[{"answer": None, "results": []}])
    search = _search_module()
    monkeypatch.setattr(search.httpx, "AsyncClient", lambda: client)

    tool = search.TavilySearchTool(api_key="tavily-key")
    await tool.run({"query": "close owned client"})
    await tool.aclose()

    assert client.closed is True


@pytest.mark.asyncio
async def test_open_meteo_weather_calls_geocoding_then_forecast_and_returns_current_weather():
    client = FakeHttpClient(
        get_payloads=[
            {
                "results": [
                    {
                        "name": "Beijing",
                        "latitude": 39.9042,
                        "longitude": 116.4074,
                    }
                ]
            },
            {
                "current": {
                    "temperature_2m": 25.5,
                    "relative_humidity_2m": 60,
                    "weather_code": 3,
                    "wind_speed_10m": 12.4,
                },
                "current_units": {
                    "temperature_2m": "°C",
                    "relative_humidity_2m": "%",
                    "wind_speed_10m": "km/h",
                },
            },
        ]
    )
    tool = _weather_module().OpenMeteoWeatherTool(http_client=client)

    result = await tool.run({"location": "Beijing", "unit": "celsius"})

    assert [call["url"] for call in client.get_calls] == [
        "https://geocoding-api.open-meteo.com/v1/search",
        "https://api.open-meteo.com/v1/forecast",
    ]
    assert client.get_calls[0]["params"]["name"] == "Beijing"
    assert client.get_calls[1]["params"]["latitude"] == 39.9042
    assert client.get_calls[1]["params"]["longitude"] == 116.4074
    assert "temperature_2m" in client.get_calls[1]["params"]["current"]
    assert result == {
        "location": {
            "name": "Beijing",
            "lat": 39.9042,
            "lon": 116.4074,
        },
        "current": {
            "temperature": 25.5,
            "temperature_unit": "°C",
            "humidity": 60,
            "humidity_unit": "%",
            "weather_code": 3,
            "wind_speed": 12.4,
            "wind_speed_unit": "km/h",
        },
    }


@pytest.mark.asyncio
async def test_open_meteo_weather_location_not_found_raises_chinese_value_error():
    client = FakeHttpClient(get_payloads=[{"results": []}])
    tool = _weather_module().OpenMeteoWeatherTool(http_client=client)

    with pytest.raises(ValueError) as exc_info:
        await tool.run({"location": "missing-place"})

    assert "未找到" in str(exc_info.value)
    assert "missing-place" in str(exc_info.value)


@pytest.mark.asyncio
async def test_open_meteo_weather_defaults_and_client_ownership(monkeypatch):
    client = FakeHttpClient(
        get_payloads=[
            {"results": [{"name": "Shanghai", "latitude": 31.23, "longitude": 121.47}]},
            {"current": {}, "current_units": {}},
        ]
    )
    weather = _weather_module()
    monkeypatch.setattr(weather.httpx, "AsyncClient", lambda: client)

    tool = weather.OpenMeteoWeatherTool()
    assert [(p.name, p.required, p.default) for p in tool.parameters] == [
        ("location", True, None),
        ("unit", False, "celsius"),
        ("target_date", False, None),
        ("days_ahead", False, None),
        ("timezone", False, "auto"),
    ]

    await tool.run({"location": "Shanghai"})
    await tool.aclose()

    assert client.get_calls[1]["params"]["temperature_unit"] == "celsius"
    assert client.closed is True

    injected_client = FakeHttpClient(get_payloads=[])
    injected_tool = weather.OpenMeteoWeatherTool(http_client=injected_client)
    await injected_tool.aclose()
    assert injected_client.closed is False


@pytest.mark.asyncio
async def test_current_time_tool_returns_asia_shanghai_now_by_default():
    time_tool = _time_module().CurrentTimeTool(
        now_provider=lambda: datetime(2026, 8, 12, 4, 30, 0, tzinfo=UTC),
    )

    result = await time_tool.run({})

    assert [(p.name, p.required, p.default) for p in time_tool.parameters] == [
        ("timezone", False, "Asia/Shanghai"),
    ]
    assert result["timezone"] == "Asia/Shanghai"
    assert result["utc_offset"] == "+08:00"
    assert result["date"] == "2026-08-12"
    assert result["datetime"] == "2026-08-12T12:30:00+08:00"


@pytest.mark.asyncio
async def test_open_meteo_weather_accepts_target_date_and_returns_daily_forecast():
    client = FakeHttpClient(
        get_payloads=[
            {"results": [{"name": "Hefei", "latitude": 31.82, "longitude": 117.23}]},
            {
                "daily": {
                    "time": ["2026-08-14"],
                    "weather_code": [61],
                    "temperature_2m_max": [33.5],
                    "temperature_2m_min": [25.0],
                    "precipitation_probability_max": [70],
                    "wind_speed_10m_max": [18.4],
                },
                "daily_units": {
                    "temperature_2m_max": "°C",
                    "temperature_2m_min": "°C",
                    "precipitation_probability_max": "%",
                    "wind_speed_10m_max": "km/h",
                },
            },
        ]
    )
    tool = _weather_module().OpenMeteoWeatherTool(http_client=client)

    result = await tool.run({"location": "合肥", "target_date": "2026-08-14"})

    forecast_params = client.get_calls[1]["params"]
    assert forecast_params["daily"] == (
        "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,wind_speed_10m_max"
    )
    assert forecast_params["start_date"] == "2026-08-14"
    assert forecast_params["end_date"] == "2026-08-14"
    assert forecast_params["timezone"] == "auto"
    assert result == {
        "location": {
            "name": "Hefei",
            "lat": 31.82,
            "lon": 117.23,
        },
        "forecast": {
            "date": "2026-08-14",
            "weather_code": 61,
            "temperature_max": 33.5,
            "temperature_min": 25.0,
            "temperature_unit": "°C",
            "precipitation_probability_max": 70,
            "precipitation_probability_unit": "%",
            "wind_speed_max": 18.4,
            "wind_speed_unit": "km/h",
        },
    }


@pytest.mark.asyncio
async def test_open_meteo_weather_converts_days_ahead_to_target_date():
    client = FakeHttpClient(
        get_payloads=[
            {"results": [{"name": "Hefei", "latitude": 31.82, "longitude": 117.23}]},
            {
                "daily": {
                    "time": ["2026-08-14"],
                    "weather_code": [3],
                    "temperature_2m_max": [34.0],
                    "temperature_2m_min": [26.0],
                    "precipitation_probability_max": [20],
                    "wind_speed_10m_max": [10.0],
                },
                "daily_units": {
                    "temperature_2m_max": "°C",
                    "temperature_2m_min": "°C",
                    "precipitation_probability_max": "%",
                    "wind_speed_10m_max": "km/h",
                },
            },
        ]
    )
    tool = _weather_module().OpenMeteoWeatherTool(
        http_client=client,
        now_provider=lambda: datetime(2026, 8, 12, 8, 0, 0, tzinfo=UTC),
    )

    result = await tool.run({"location": "合肥", "days_ahead": 2, "timezone": "Asia/Shanghai"})

    assert client.get_calls[1]["params"]["start_date"] == "2026-08-14"
    assert result["forecast"]["date"] == "2026-08-14"


@pytest.mark.asyncio
async def test_open_meteo_weather_converts_days_ahead_from_local_timezone_date():
    client = FakeHttpClient(
        get_payloads=[
            {"results": [{"name": "Hefei", "latitude": 31.82, "longitude": 117.23}]},
            {
                "daily": {
                    "time": ["2026-08-14"],
                    "weather_code": [3],
                    "temperature_2m_max": [34.0],
                    "temperature_2m_min": [26.0],
                    "precipitation_probability_max": [20],
                    "wind_speed_10m_max": [10.0],
                },
                "daily_units": {
                    "temperature_2m_max": "°C",
                    "temperature_2m_min": "°C",
                    "precipitation_probability_max": "%",
                    "wind_speed_10m_max": "km/h",
                },
            },
        ]
    )
    tool = _weather_module().OpenMeteoWeatherTool(
        http_client=client,
        now_provider=lambda: datetime(2026, 8, 11, 18, 30, 0, tzinfo=UTC),
    )

    result = await tool.run({"location": "合肥", "days_ahead": 2, "timezone": "Asia/Shanghai"})

    assert client.get_calls[1]["params"]["start_date"] == "2026-08-14"
    assert result["forecast"]["date"] == "2026-08-14"


def test_open_meteo_weather_tool_name_matches_public_spec():
    tool = _weather_module().OpenMeteoWeatherTool(http_client=FakeHttpClient())

    assert tool.name == "get_weather"


@pytest.mark.asyncio
async def test_open_meteo_weather_can_be_invoked_through_registry_by_spec_name():
    client = FakeHttpClient(
        get_payloads=[
            {"results": [{"name": "Beijing", "latitude": 39.9042, "longitude": 116.4074}]},
            {
                "current": {
                    "temperature_2m": 22.0,
                    "relative_humidity_2m": 55,
                    "weather_code": 1,
                    "wind_speed_10m": 8.0,
                },
                "current_units": {
                    "temperature_2m": "°C",
                    "relative_humidity_2m": "%",
                    "wind_speed_10m": "km/h",
                },
            },
        ]
    )
    registry = _registry_module().ToolRegistry()
    registry.register(_weather_module().OpenMeteoWeatherTool(http_client=client))

    schema = registry.to_qwen_tools()
    result = await registry.invoke("get_weather", {"location": "Beijing"})

    assert schema[0]["function"]["name"] == "get_weather"
    assert result.success is True
    assert result.data["location"]["name"] == "Beijing"
    assert result.data["current"]["temperature"] == 22.0


@pytest.mark.asyncio
async def test_open_meteo_weather_request_error_returns_stable_chinese_registry_message():
    errors = importlib.import_module("src.tools.errors")
    registry = _registry_module().ToolRegistry()
    registry.register(_weather_module().OpenMeteoWeatherTool(http_client=FailingGetClient()))

    result = await registry.invoke("get_weather", {"location": "Beijing"})

    assert result.success is False
    assert result.error_code == errors.ToolErrorCode.EXECUTION_ERROR
    assert "Open-Meteo 天气请求失败" in result.message
