from __future__ import annotations

import asyncio
import time
from typing import Any

from src.tools.base import BaseTool
from src.tools.circuit_breaker import CircuitBreaker
from src.tools.errors import ToolErrorCode
from src.tools.response import ToolResponse


class ToolRegistry:
    def __init__(self, timeout_seconds: float = 180, failure_threshold: int = 3):
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker = CircuitBreaker(failure_threshold=failure_threshold)
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("工具名称不能为空。")
        self._tools[tool.name] = tool

    def list_tools(self) -> list[str]:
        return list(self._tools)

    def to_qwen_tools(self) -> list[dict[str, Any]]:
        return [self._to_qwen_tool(tool) for tool in self._tools.values()]

    async def invoke(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResponse:
        started_at = time.perf_counter()
        tool = self._tools.get(tool_name)
        if tool is None:
            return self._error_response(
                ToolErrorCode.NOT_FOUND,
                f"未找到工具：{tool_name}",
                started_at,
            )

        if not self.circuit_breaker.allow_request(tool_name):
            return self._error_response(
                ToolErrorCode.CIRCUIT_OPEN,
                f"工具 {tool_name} 已熔断，请稍后重试。",
                started_at,
            )

        prepared_arguments, missing_arguments = self._prepare_arguments(tool, arguments or {})
        if missing_arguments:
            missing = "、".join(missing_arguments)
            return self._error_response(
                ToolErrorCode.INVALID_ARGUMENTS,
                f"缺少必填参数：{missing}",
                started_at,
            )

        try:
            data = await asyncio.wait_for(
                tool.run(prepared_arguments),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            self.circuit_breaker.record_failure(tool_name)
            return self._error_response(
                ToolErrorCode.TIMEOUT,
                f"工具 {tool_name} 执行超时。",
                started_at,
            )
        except Exception as exc:
            self.circuit_breaker.record_failure(tool_name)
            return self._error_response(
                ToolErrorCode.EXECUTION_ERROR,
                f"工具 {tool_name} 执行失败：{exc}",
                started_at,
            )

        self.circuit_breaker.record_success(tool_name)
        return ToolResponse(
            success=True,
            data=data,
            message="调用成功",
            elapsed_ms=self._elapsed_ms(started_at),
        )

    @staticmethod
    def _to_qwen_tool(tool: BaseTool) -> dict[str, Any]:
        properties = {
            parameter.name: {
                "type": parameter.type,
                "description": parameter.description,
            }
            for parameter in tool.parameters
        }
        required = [parameter.name for parameter in tool.parameters if parameter.required]
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @staticmethod
    def _prepare_arguments(
        tool: BaseTool,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        prepared = dict(arguments)
        missing = []

        for parameter in tool.parameters:
            if parameter.name in prepared:
                continue
            if parameter.required:
                missing.append(parameter.name)
                continue
            prepared[parameter.name] = parameter.default

        return prepared, missing

    @classmethod
    def _error_response(
        cls,
        error_code: ToolErrorCode,
        message: str,
        started_at: float,
    ) -> ToolResponse:
        return ToolResponse(
            success=False,
            data=None,
            error_code=error_code,
            message=message,
            elapsed_ms=cls._elapsed_ms(started_at),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (time.perf_counter() - started_at) * 1000
