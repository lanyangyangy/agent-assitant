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

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error_code": self.error_code.value if self.error_code is not None else None,
            "message": self.message,
            "elapsed_ms": self.elapsed_ms,
        }
