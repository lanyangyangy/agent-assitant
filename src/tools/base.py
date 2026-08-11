from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class BaseTool:
    name: str
    description: str
    parameters: list[ToolParameter] = []

    async def run(self, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError("工具必须实现 run(arguments)。")
