from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager

from src.agents.qwen_client import QwenClient
from src.core.config import Settings
from src.main import create_app
from src.tools.calculator import CalculatorTool
from src.tools.registry import ToolRegistry
from src.tools.search import TavilySearchTool
from src.tools.weather import OpenMeteoWeatherTool


pytestmark = pytest.mark.integration


def _settings_from_env_file() -> Settings:
    return Settings(_env_file=".env")


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in raw.strip().split("\n\n"):
        event_name = None
        event_data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                event_data = json.loads(line.removeprefix("data: "))
        if event_name is not None:
            events.append({"event": event_name, "data": event_data})
    return events


def _calculator_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    return registry


def _qwen_client(settings: Settings) -> QwenClient:
    return QwenClient(
        api_key=settings.dashscope_api_key or "",
        base_url=settings.dashscope_base_url,
        model=settings.llm_model_id,
    )


@pytest.mark.asyncio
async def test_real_open_meteo_weather_smoke():
    tool = OpenMeteoWeatherTool()

    try:
        result = await tool.run({"location": "Beijing", "unit": "celsius"})
    finally:
        await tool.aclose()

    assert result["location"]["name"]
    assert result["location"]["lat"] is not None
    assert result["location"]["lon"] is not None
    assert result["current"]["temperature"] is not None
    assert isinstance(result["current"]["temperature"], int | float)


@pytest.mark.asyncio
async def test_real_tavily_search_smoke():
    settings = _settings_from_env_file()
    if not settings.tavily_api_key:
        pytest.skip("缺少 TAVILY_API_KEY，跳过真实 Tavily integration smoke test。")

    tool = TavilySearchTool(settings.tavily_api_key)
    try:
        result = await tool.run(
            {"query": "Qwen function calling documentation", "max_results": 3}
        )
    finally:
        await tool.aclose()

    assert result["results"]
    assert any(item.get("url") for item in result["results"])


@pytest.mark.asyncio
async def test_real_qwen_tool_call_smoke():
    settings = _settings_from_env_file()
    if not settings.dashscope_api_key:
        pytest.skip("缺少 DASHSCOPE_API_KEY，跳过真实 Qwen 工具调用 smoke test。")

    registry = _calculator_registry()
    client = _qwen_client(settings)

    try:
        message = await client.create_completion(
            messages=[
                {
                    "role": "user",
                    "content": "必须调用 calculator 工具计算 19 * 23，只返回工具调用。",
                }
            ],
            tools=registry.to_qwen_tools(),
            tool_choice={"type": "function", "function": {"name": "calculator"}},
        )
    finally:
        await client.aclose()

    tool_calls = message.get("tool_calls") or []
    assert tool_calls
    assert tool_calls[0]["function"]["name"] == "calculator"


@pytest.mark.asyncio
async def test_real_qwen_stream_smoke():
    settings = _settings_from_env_file()
    if not settings.dashscope_api_key:
        pytest.skip("缺少 DASHSCOPE_API_KEY，跳过真实 Qwen 流式输出 smoke test。")

    client = _qwen_client(settings)
    tokens: list[str] = []

    try:
        async for token in client.stream_completion(
            [{"role": "user", "content": "用中文简短回答：1+1 等于几？"}]
        ):
            tokens.append(token)
            break
    finally:
        await client.aclose()

    assert tokens
    assert tokens[0].strip()


@pytest.mark.asyncio
async def test_real_api_local_e2e_smoke(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        APP_DATA_DIR=tmp_path,
        DASHSCOPE_API_KEY=None,
        TAVILY_API_KEY=None,
    )
    app = create_app(data_dir=tmp_path, settings=settings)

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            created = await client.post("/sessions", headers={"X-User-Id": "integration"})
            session_id = created.json()["session_id"]

            response = await client.post(
                "/chat/stream",
                headers={"X-User-Id": "integration"},
                json={"session_id": session_id, "message": "19*23"},
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    event_names = [event["event"] for event in _parse_sse(response.text)]
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert event_names[-1] == "message_end"
