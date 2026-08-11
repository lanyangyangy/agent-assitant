from __future__ import annotations

from collections.abc import Iterable

from src.core.session_store import MessageRecord


def format_history(history: Iterable[MessageRecord]) -> str:
    lines = []
    for message in history:
        content = message.content.strip()
        if not content:
            continue
        lines.append(f"{message.role}: {content}")
    return "\n".join(lines)
