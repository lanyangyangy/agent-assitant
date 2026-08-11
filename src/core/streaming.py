from __future__ import annotations

import json

from src.core.agent import AgentEvent


def format_sse(event: AgentEvent) -> str:
    data = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.type}\ndata: {data}\n\n"
