from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from asgi_lifespan import LifespanManager

from src.core.agent import AgentEvent
from src.tools.base import BaseTool
from src.tools.time_tool import CurrentTimeTool


def _parse_sse(raw: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in raw.strip().split("\n\n"):
        event_name = None
        event_data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                event_data = json.loads(line.removeprefix("data: "))
        if event_name is not None:
            events.append({"event": event_name, "data": event_data})
    return events


async def test_chat_stream_runs_local_calculator_tool_call(client):
    created = await client.post("/sessions", headers={"X-User-Id": "alice"})
    session_id = created.json()["session_id"]

    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": session_id, "message": "请计算 6*7", "metadata": {"source": "api-test"}},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    event_names = [event["event"] for event in events]
    assert event_names[0] == "message_start"
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "token" in event_names
    assert event_names[-1] == "message_end"

    tool_call = next(event for event in events if event["event"] == "tool_call")
    assert tool_call["data"]["name"] == "calculator"

    tool_result = next(event for event in events if event["event"] == "tool_result")
    result = tool_result["data"]["result"]
    assert result["success"] is True
    assert result["data"]["result"] == 42


async def test_chat_stream_chains_time_then_weather_for_relative_date_request(app):
    weather_tool = _FakeForecastWeatherTool()

    async with LifespanManager(app):
        app.state.tool_registry.register(
            CurrentTimeTool(
                now_provider=lambda: datetime(2026, 8, 12, 4, 30, 0, tzinfo=UTC),
            )
        )
        app.state.tool_registry.register(weather_tool)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            created = await client.post("/sessions", headers={"X-User-Id": "alice"})
            session_id = created.json()["session_id"]

            response = await client.post(
                "/chat/stream",
                headers={"X-User-Id": "alice"},
                json={"session_id": session_id, "message": "后天合肥的天气怎么样"},
            )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    event_names = [event["event"] for event in events]
    assert event_names[0] == "message_start"
    assert event_names.count("tool_call") == 2
    assert event_names.count("tool_result") == 2
    assert event_names[-1] == "message_end"

    tool_calls = [event for event in events if event["event"] == "tool_call"]
    assert [call["data"]["name"] for call in tool_calls] == ["get_time", "get_weather"]
    assert tool_calls[0]["data"]["arguments"]
    assert "target_date" in tool_calls[1]["data"]["arguments"]
    assert "2026-08-14" in tool_calls[1]["data"]["arguments"]
    assert weather_tool.calls == [
        {
            "location": "合肥",
            "target_date": "2026-08-14",
            "timezone": "Asia/Shanghai",
        }
    ]

    tool_results = [event for event in events if event["event"] == "tool_result"]
    assert tool_results[0]["data"]["result"]["success"] is True
    assert tool_results[1]["data"]["result"]["success"] is True
    assert "forecast" in tool_results[1]["data"]["result"]["data"]

    final_tokens = [event["data"]["content"] for event in events if event["event"] == "token"]
    assert final_tokens
    assert "合肥" in "".join(final_tokens)
    assert "2026-08-14" in "".join(final_tokens)


@pytest.mark.parametrize(
    ("message", "expected_result"),
    [
        ("请计算6*7", 42),
        ("2+2等于几", 4),
        ("请帮我算(3+4)*5", 35),
    ],
)
async def test_chat_stream_extracts_chinese_adjacent_math_expressions(
    client,
    message,
    expected_result,
):
    created = await client.post("/sessions", headers={"X-User-Id": "alice"})
    session_id = created.json()["session_id"]

    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": session_id, "message": message},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    tool_result = next(event for event in events if event["event"] == "tool_result")
    result = tool_result["data"]["result"]
    assert result["success"] is True
    assert result["data"]["result"] == expected_result


async def test_chat_stream_converts_unhandled_agent_exception_to_sse_error(app):
    async with LifespanManager(app):
        app.state.agent = _RaisingAgent()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/chat/stream",
                headers={"X-User-Id": "alice"},
                json={"session_id": "s1", "message": "你好"},
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [event["event"] for event in events] == ["error"]
    assert "聊天流中断" in events[0]["data"]["message"]


@pytest.mark.parametrize(
    "body",
    [
        {"session_id": "s1"},
        {"session_id": "s1", "message": "   "},
        {"session_id": "s1", "message": "你好", "extra": "not-allowed"},
        {"session_id": "s1", "message": "你好", "metadata": "bad"},
    ],
)
async def test_chat_stream_validation_errors_use_stable_chinese_detail(client, body):
    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json=body,
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "请求参数校验失败。"
    assert payload["errors"]
    assert all("loc" in error for error in payload["errors"])


async def test_chat_stream_returns_sse_error_for_missing_session(client):
    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": "missing-session", "message": "你好"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [event["event"] for event in events] == ["error"]
    assert "会话" in events[0]["data"]["message"]


class _RaisingAgent:
    async def stream_chat(self, *args, **kwargs):
        raise RuntimeError("agent exploded")
        yield AgentEvent("token", {"content": "不会到达"})


class _FakeForecastWeatherTool(BaseTool):
    name = "get_weather"
    description = "测试用天气工具。"
    parameters = []

    def __init__(self):
        self.calls = []

    async def run(self, arguments):
        self.calls.append(dict(arguments))
        return {
            "location": {"name": arguments["location"], "lat": 31.82, "lon": 117.23},
            "forecast": {
                "date": arguments["target_date"],
                "weather_code": 3,
                "temperature_max": 34.0,
                "temperature_min": 26.0,
                "temperature_unit": "°C",
                "precipitation_probability_max": 20,
                "precipitation_probability_unit": "%",
                "wind_speed_max": 10.0,
                "wind_speed_unit": "km/h",
            },
        }
