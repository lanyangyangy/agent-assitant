from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.tools.errors import ToolErrorCode


@dataclass(frozen=True)
class ToolResponse:
    success: bool
    data: Any = None
    error_code: ToolErrorCode | None = None
    message: str = ""
    elapsed_ms: float = 0.0
