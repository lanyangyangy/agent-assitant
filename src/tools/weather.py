from __future__ import annotations

from typing import Any

import httpx

from src.tools.base import BaseTool, ToolParameter
from src.tools.errors import ToolInputError


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"


class OpenMeteoWeatherTool(BaseTool):
    name = "get_weather"
    description = "使用 Open-Meteo 查询指定地点的当前天气。"
    parameters = [
        ToolParameter("location", "string", "城市、地区或地点名称。"),
        ToolParameter("unit", "string", "温度单位：celsius 或 fahrenheit。", required=False, default="celsius"),
    ]

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        location = arguments.get("location")
        if not isinstance(location, str) or not location.strip():
            raise ToolInputError("参数 location 必须是非空字符串。")

        unit = arguments.get("unit", "celsius")
        if unit not in {"celsius", "fahrenheit"}:
            raise ToolInputError("参数 unit 只能是 celsius 或 fahrenheit。")

        geocoding_response = await self._client.get(
            GEOCODING_URL,
            params={
                "name": location,
                "count": 1,
                "language": "zh",
                "format": "json",
            },
        )
        geocoding_response.raise_for_status()
        geocoding_payload = geocoding_response.json()
        locations = geocoding_payload.get("results") or []
        if not locations:
            raise ToolInputError(f"未找到位置：{location}")

        found_location = locations[0]
        lat = found_location["latitude"]
        lon = found_location["longitude"]
        name = found_location.get("name", location)

        forecast_response = await self._client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": CURRENT_FIELDS,
                "temperature_unit": unit,
            },
        )
        forecast_response.raise_for_status()
        forecast_payload = forecast_response.json()
        current = forecast_payload.get("current", {})
        current_units = forecast_payload.get("current_units", {})

        return {
            "location": {
                "name": name,
                "lat": lat,
                "lon": lon,
            },
            "current": {
                "temperature": current.get("temperature_2m"),
                "temperature_unit": current_units.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "humidity_unit": current_units.get("relative_humidity_2m"),
                "weather_code": current.get("weather_code"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_speed_unit": current_units.get("wind_speed_10m"),
            },
        }

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
