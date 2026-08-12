from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Callable

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.tools.base import BaseTool, ToolParameter
from src.tools.errors import ToolInputError


@dataclass(frozen=True)
class _ResolvedTime:
    timezone_name: str
    utc_offset: str
    date: str
    datetime_text: str


_FIXED_TIMEZONES = {
    "Asia/Shanghai": timezone(timedelta(hours=8)),
    "Asia/Chongqing": timezone(timedelta(hours=8)),
    "UTC": UTC,
}


class CurrentTimeTool(BaseTool):
    name = "get_time"
    description = "获取指定时区的当前日期和时间。"
    parameters = [
        ToolParameter("timezone", "string", "IANA 时区名称。", required=False, default="Asia/Shanghai"),
    ]

    def __init__(self, now_provider: Callable[[], datetime] | None = None):
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    async def run(self, arguments: dict[str, Any]) -> dict[str, str]:
        timezone_name = arguments.get("timezone", "Asia/Shanghai")
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ToolInputError("参数 timezone 必须是非空字符串。")

        resolved = self._resolve_time(timezone_name.strip())
        return {
            "timezone": resolved.timezone_name,
            "utc_offset": resolved.utc_offset,
            "date": resolved.date,
            "datetime": resolved.datetime_text,
        }

    def _resolve_time(self, timezone_name: str) -> _ResolvedTime:
        now_utc = self._now_provider()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        else:
            now_utc = now_utc.astimezone(UTC)

        tz = _load_timezone(timezone_name)
        localized = now_utc.astimezone(tz)
        offset = localized.utcoffset() or timedelta(0)
        return _ResolvedTime(
            timezone_name=timezone_name,
            utc_offset=_format_utc_offset(offset),
            date=localized.date().isoformat(),
            datetime_text=localized.isoformat(timespec="seconds"),
        )


def _format_utc_offset(offset: timedelta) -> str:
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _load_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        fallback = _FIXED_TIMEZONES.get(timezone_name)
        if fallback is None:
            raise ToolInputError(f"未找到时区：{timezone_name}") from exc
        return fallback
