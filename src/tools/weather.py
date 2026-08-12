from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import httpx
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.tools.base import BaseTool, ToolParameter
from src.tools.errors import ToolInputError


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,wind_speed_10m_max"
)
_FIXED_TIMEZONES = {
    "Asia/Shanghai": timezone(timedelta(hours=8)),
    "Asia/Chongqing": timezone(timedelta(hours=8)),
    "UTC": UTC,
}


class OpenMeteoWeatherTool(BaseTool):
    name = "get_weather"
    description = "使用 Open-Meteo 查询指定地点的天气。"
    parameters = [
        ToolParameter("location", "string", "城市、地区或地点名称。"),
        ToolParameter("unit", "string", "温度单位：celsius 或 fahrenheit。", required=False, default="celsius"),
        ToolParameter("target_date", "string", "目标日期，格式为 YYYY-MM-DD。", required=False, default=None),
        ToolParameter("days_ahead", "integer", "相对今天向后推几天。", required=False, default=None),
        ToolParameter("timezone", "string", "IANA 时区名称。", required=False, default="auto"),
    ]

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self._client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        location = arguments.get("location")
        if not isinstance(location, str) or not location.strip():
            raise ToolInputError("参数 location 必须是非空字符串。")

        unit = arguments.get("unit", "celsius")
        if unit not in {"celsius", "fahrenheit"}:
            raise ToolInputError("参数 unit 只能是 celsius 或 fahrenheit。")

        timezone_name = arguments.get("timezone", "auto")
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ToolInputError("参数 timezone 必须是非空字符串。")
        timezone_name = timezone_name.strip()
        if timezone_name != "auto":
            _load_timezone(timezone_name)

        target_date = self._resolve_target_date(arguments, timezone_name)

        location_data = await self._lookup_location(location)
        if target_date is None:
            return await self._fetch_current_weather(location_data, unit, timezone_name)
        return await self._fetch_daily_forecast(location_data, unit, timezone_name, target_date)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _resolve_target_date(self, arguments: dict[str, Any], timezone_name: str) -> date | None:
        target_date = arguments.get("target_date")
        days_ahead = arguments.get("days_ahead")

        if target_date is not None and days_ahead is not None:
            raise ToolInputError("target_date 和 days_ahead 只能提供一个。")

        if target_date is not None:
            if not isinstance(target_date, str) or not target_date.strip():
                raise ToolInputError("参数 target_date 必须是非空字符串。")
            try:
                return date.fromisoformat(target_date.strip())
            except ValueError as exc:
                raise ToolInputError("参数 target_date 必须是 YYYY-MM-DD 格式。") from exc

        if days_ahead is None:
            return None

        if isinstance(days_ahead, bool) or not isinstance(days_ahead, int):
            raise ToolInputError("参数 days_ahead 必须是整数。")
        if days_ahead < 0:
            raise ToolInputError("参数 days_ahead 不能为负数。")

        return self._current_local_date(timezone_name) + timedelta(days=days_ahead)

    async def _lookup_location(self, location: str) -> dict[str, Any]:
        try:
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
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "未知"
            raise RuntimeError(f"Open-Meteo 天气请求失败：HTTP {status_code}。") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Open-Meteo 天气请求失败：网络请求异常。") from exc

        geocoding_payload = geocoding_response.json()
        locations = geocoding_payload.get("results") or []
        if not locations:
            raise ToolInputError(f"未找到位置：{location}")

        found_location = locations[0]
        return {
            "name": found_location.get("name", location),
            "lat": found_location["latitude"],
            "lon": found_location["longitude"],
        }

    async def _fetch_current_weather(
        self,
        location_data: dict[str, Any],
        unit: str,
        timezone_name: str,
    ) -> dict[str, Any]:
        lat = location_data["lat"]
        lon = location_data["lon"]
        try:
            forecast_response = await self._client.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": CURRENT_FIELDS,
                    "timezone": timezone_name,
                    "temperature_unit": unit,
                },
            )
            forecast_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "未知"
            raise RuntimeError(f"Open-Meteo 天气请求失败：HTTP {status_code}。") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Open-Meteo 天气请求失败：网络请求异常。") from exc

        forecast_payload = forecast_response.json()
        current = forecast_payload.get("current", {})
        current_units = forecast_payload.get("current_units", {})
        return {
            "location": location_data,
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

    async def _fetch_daily_forecast(
        self,
        location_data: dict[str, Any],
        unit: str,
        timezone_name: str,
        target_date: date,
    ) -> dict[str, Any]:
        lat = location_data["lat"]
        lon = location_data["lon"]
        try:
            forecast_response = await self._client.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": DAILY_FIELDS,
                    "timezone": timezone_name,
                    "temperature_unit": unit,
                    "start_date": target_date.isoformat(),
                    "end_date": target_date.isoformat(),
                },
            )
            forecast_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "未知"
            raise RuntimeError(f"Open-Meteo 天气请求失败：HTTP {status_code}。") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Open-Meteo 天气请求失败：网络请求异常。") from exc

        forecast_payload = forecast_response.json()
        daily = forecast_payload.get("daily", {})
        daily_units = forecast_payload.get("daily_units", {})
        index = self._find_date_index(daily.get("time", []), target_date.isoformat())
        if index is None:
            raise RuntimeError(f"Open-Meteo 天气请求失败：未返回目标日期 {target_date.isoformat()} 的预报。")

        return {
            "location": location_data,
            "forecast": {
                "date": target_date.isoformat(),
                "weather_code": _pick_daily_value(daily, "weather_code", index),
                "temperature_max": _pick_daily_value(daily, "temperature_2m_max", index),
                "temperature_min": _pick_daily_value(daily, "temperature_2m_min", index),
                "temperature_unit": daily_units.get("temperature_2m_max"),
                "precipitation_probability_max": _pick_daily_value(
                    daily,
                    "precipitation_probability_max",
                    index,
                ),
                "precipitation_probability_unit": daily_units.get("precipitation_probability_max"),
                "wind_speed_max": _pick_daily_value(daily, "wind_speed_10m_max", index),
                "wind_speed_unit": daily_units.get("wind_speed_10m_max"),
            },
        }

    def _current_local_date(self, timezone_name: str) -> date:
        now = self._now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        if timezone_name == "auto":
            return now.date()

        return now.astimezone(_load_timezone(timezone_name)).date()

    @staticmethod
    def _find_date_index(times: list[Any], target_date: str) -> int | None:
        for index, value in enumerate(times):
            if str(value) == target_date:
                return index
        return None


def _load_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        fallback = _FIXED_TIMEZONES.get(timezone_name)
        if fallback is None:
            raise ToolInputError(f"未找到时区：{timezone_name}") from exc
        return fallback


def _pick_daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    values = daily.get(key) or []
    if index < 0 or index >= len(values):
        return None
    return values[index]
