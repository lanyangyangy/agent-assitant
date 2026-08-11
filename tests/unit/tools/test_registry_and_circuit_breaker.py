from __future__ import annotations

import asyncio
import importlib
from typing import Any

import pytest


def _tool_modules():
    base = importlib.import_module("src.tools.base")
    circuit_breaker = importlib.import_module("src.tools.circuit_breaker")
    errors = importlib.import_module("src.tools.errors")
    registry = importlib.import_module("src.tools.registry")
    response = importlib.import_module("src.tools.response")
    return base, circuit_breaker, errors, registry, response


def _make_echo_tool_class():
    base, *_ = _tool_modules()

    class EchoTool(base.BaseTool):
        name = "echo"
        description = "回显文本"
        parameters = [
            base.ToolParameter("text", "string", "要回显的文本"),
            base.ToolParameter("suffix", "string", "追加后缀", required=False, default="!"),
        ]

        async def run(self, arguments: dict[str, Any]) -> dict[str, str]:
            return {"value": arguments["text"] + arguments["suffix"]}

    return EchoTool


@pytest.mark.asyncio
async def test_registry_outputs_qwen_compatible_schema_and_invokes_tool():
    _, _, errors, registry, response = _tool_modules()
    registry_obj = registry.ToolRegistry()
    echo_tool = _make_echo_tool_class()()
    registry_obj.register(echo_tool)

    assert registry_obj.list_tools() == [echo_tool]
    assert registry_obj.list_tool_names() == ["echo"]
    assert registry_obj.to_qwen_tools() == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "回显文本",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要回显的文本"},
                        "suffix": {"type": "string", "description": "追加后缀"},
                    },
                    "required": ["text"],
                },
            },
        }
    ]

    result = await registry_obj.invoke("echo", {"text": "你好"})

    assert isinstance(result, response.ToolResponse)
    assert result.success is True
    assert result.data == {"value": "你好!"}
    assert result.error_code is None
    assert result.message == "调用成功"
    assert result.elapsed_ms >= 0
    assert errors.ToolErrorCode.INVALID_ARGUMENTS.value == "INVALID_ARGUMENTS"


def test_tool_response_to_dict_uses_stable_error_code_value():
    _, _, errors, _, response = _tool_modules()

    result = response.ToolResponse(
        success=False,
        data=None,
        error_code=errors.ToolErrorCode.INVALID_ARGUMENTS,
        message="参数无效",
        elapsed_ms=1.5,
    )

    assert result.to_dict() == {
        "success": False,
        "data": None,
        "error_code": "INVALID_ARGUMENTS",
        "message": "参数无效",
        "elapsed_ms": 1.5,
    }


@pytest.mark.asyncio
async def test_missing_required_argument_returns_invalid_arguments_with_chinese_message():
    _, _, errors, registry, _ = _tool_modules()
    registry_obj = registry.ToolRegistry()
    registry_obj.register(_make_echo_tool_class()())

    result = await registry_obj.invoke("echo", {})

    assert result.success is False
    assert result.data is None
    assert result.error_code == errors.ToolErrorCode.INVALID_ARGUMENTS
    assert "缺少" in result.message
    assert "text" in result.message


@pytest.mark.asyncio
async def test_non_mapping_arguments_return_invalid_arguments_without_raising():
    _, _, errors, registry, _ = _tool_modules()
    registry_obj = registry.ToolRegistry()
    registry_obj.register(_make_echo_tool_class()())

    result = await registry_obj.invoke("echo", "not-a-mapping")

    assert result.success is False
    assert result.data is None
    assert result.error_code == errors.ToolErrorCode.INVALID_ARGUMENTS
    assert "参数" in result.message
    assert "对象" in result.message


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found():
    _, _, errors, registry, _ = _tool_modules()

    result = await registry.ToolRegistry().invoke("missing_tool", {})

    assert result.success is False
    assert result.data is None
    assert result.error_code == errors.ToolErrorCode.NOT_FOUND
    assert "missing_tool" in result.message


def test_circuit_breaker_opens_after_three_failures_and_success_resets():
    _, circuit_breaker, _, _, _ = _tool_modules()
    breaker = circuit_breaker.CircuitBreaker(failure_threshold=3)

    assert breaker.allow_request("demo") is True
    breaker.record_failure("demo")
    breaker.record_failure("demo")
    assert breaker.allow_request("demo") is True

    breaker.record_failure("demo")

    assert breaker.allow_request("demo") is False

    breaker.record_success("demo")

    assert breaker.allow_request("demo") is True


def test_circuit_breaker_allows_one_half_open_probe_after_recovery_timeout(monkeypatch):
    _, circuit_breaker, _, _, _ = _tool_modules()
    now = 100.0
    monkeypatch.setattr(circuit_breaker.time, "monotonic", lambda: now)
    breaker = circuit_breaker.CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_seconds=5,
    )

    breaker.record_failure("api")
    breaker.record_failure("api")

    assert breaker.allow_request("api") is False

    now = 104.9
    assert breaker.allow_request("api") is False

    now = 105.0
    assert breaker.allow_request("api") is True
    assert breaker.allow_request("api") is False

    breaker.record_failure("api")
    assert breaker.allow_request("api") is False

    now = 110.0
    assert breaker.allow_request("api") is True

    breaker.record_success("api")
    assert breaker.allow_request("api") is True


@pytest.mark.asyncio
async def test_registry_returns_timeout_when_tool_runs_too_long():
    base, _, errors, registry, _ = _tool_modules()

    class SlowTool(base.BaseTool):
        name = "slow"
        description = "慢工具"
        parameters = []

        async def run(self, arguments: dict[str, Any]) -> dict[str, bool]:
            await asyncio.sleep(0.05)
            return {"finished": True}

    registry_obj = registry.ToolRegistry(timeout_seconds=0.001)
    registry_obj.register(SlowTool())

    result = await registry_obj.invoke("slow", {})

    assert result.success is False
    assert result.data is None
    assert result.error_code == errors.ToolErrorCode.TIMEOUT
    assert "超时" in result.message


@pytest.mark.asyncio
async def test_registry_returns_circuit_open_after_consecutive_execution_failures():
    base, _, errors, registry, _ = _tool_modules()

    class FailingTool(base.BaseTool):
        name = "failing"
        description = "总是失败"
        parameters = []

        async def run(self, arguments: dict[str, Any]) -> dict[str, str]:
            raise RuntimeError("执行失败")

    registry_obj = registry.ToolRegistry(failure_threshold=3)
    registry_obj.register(FailingTool())

    for _ in range(3):
        result = await registry_obj.invoke("failing", {})
        assert result.error_code == errors.ToolErrorCode.EXECUTION_ERROR

    opened = await registry_obj.invoke("failing", {})

    assert opened.success is False
    assert opened.error_code == errors.ToolErrorCode.CIRCUIT_OPEN
    assert "熔断" in opened.message
