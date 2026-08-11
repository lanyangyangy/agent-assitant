from __future__ import annotations

import json
from pathlib import Path

from src.core.agent import AgentEvent
from src.core.streaming import format_sse
from src.core.trace_logger import TraceLogger


def test_format_sse_uses_compact_utf8_json():
    event = AgentEvent("token", {"content": "你好", "index": 1})

    assert format_sse(event) == 'event: token\ndata: {"content":"你好","index":1}\n\n'


def test_trace_logger_appends_jsonl_and_html_without_escaping_chinese(tmp_path: Path):
    logger = TraceLogger(tmp_path)

    logger.log_event("session-1", AgentEvent("message_start", {"message": "开始"}))
    logger.log_event("session-1", AgentEvent("message_end", {"message": "完成"}))

    jsonl_path = tmp_path / "session-1.jsonl"
    html_path = tmp_path / "session-1.html"
    jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    html = html_path.read_text(encoding="utf-8")

    assert [json.loads(line)["type"] for line in jsonl_lines] == ["message_start", "message_end"]
    assert "开始" in jsonl_lines[0]
    assert "完成" in html
    assert html.count("<pre") == 2
