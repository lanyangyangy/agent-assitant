from __future__ import annotations

from html import escape
import json
from pathlib import Path
import re

from src.core.agent import AgentEvent


class TraceLogger:
    def __init__(self, trace_dir: Path):
        self.trace_dir = trace_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, trace_id: str, event: AgentEvent) -> None:
        safe_trace_id = self._safe_trace_id(trace_id)
        payload = {"type": event.type, "data": event.data}
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        jsonl_path = self.trace_dir / f"{safe_trace_id}.jsonl"
        html_path = self.trace_dir / f"{safe_trace_id}.html"

        with jsonl_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

        if not html_path.exists():
            html_path.write_text(
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>Agent Trace</title></head><body>\n",
                encoding="utf-8",
            )

        with html_path.open("a", encoding="utf-8") as file:
            file.write(f"<pre data-event=\"{escape(event.type)}\">{escape(line)}</pre>\n")

    @staticmethod
    def _safe_trace_id(trace_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", trace_id).strip("._")
        return safe or "trace"
