from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict[str, Any]
