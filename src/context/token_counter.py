from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]|[^\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    """轻量 token 估算，偏向稳定和便宜，不追求模型级精确。"""
    if not text:
        return 0

    return len(_TOKEN_RE.findall(text))
