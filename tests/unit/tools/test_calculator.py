from __future__ import annotations

import importlib

import pytest


def _calculator_module():
    return importlib.import_module("src.tools.calculator")


def _registry_modules():
    errors = importlib.import_module("src.tools.errors")
    registry = importlib.import_module("src.tools.registry")
    return errors, registry


@pytest.mark.asyncio
async def test_calculator_evaluates_precedence_and_parentheses():
    calculator = _calculator_module().CalculatorTool()

    result = await calculator.run({"expression": "2 + 3 * (4 + 5)"})

    assert result == {"result": 29}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("+2", 2),
        ("-2 + 5", 3),
        ("8 / 4", 2),
        ("7 // 2", 3),
        ("7 % 4", 3),
        ("2 ** 3", 8),
    ],
)
async def test_calculator_supports_basic_arithmetic(expression: str, expected: int | float):
    calculator = _calculator_module().CalculatorTool()

    result = await calculator.run({"expression": expression})

    assert result["result"] == expected


@pytest.mark.asyncio
async def test_calculator_rejects_arbitrary_code_execution():
    calculator = _calculator_module().CalculatorTool()

    with pytest.raises(ValueError) as exc_info:
        await calculator.run({"expression": "__import__('os').system('echo unsafe')"})

    assert "不允许" in str(exc_info.value)


@pytest.mark.asyncio
async def test_calculator_rejects_division_by_zero_with_chinese_message():
    calculator = _calculator_module().CalculatorTool()

    with pytest.raises(ValueError) as exc_info:
        await calculator.run({"expression": "1 / 0"})

    assert "除零" in str(exc_info.value)


@pytest.mark.asyncio
async def test_calculator_can_be_invoked_through_registry():
    errors, registry = _registry_modules()
    registry_obj = registry.ToolRegistry()
    registry_obj.register(_calculator_module().CalculatorTool())

    result = await registry_obj.invoke("calculator", {"expression": "2 ** 4"})

    assert result.success is True
    assert result.data == {"result": 16}
    assert result.error_code is None

    unsafe = await registry_obj.invoke(
        "calculator",
        {"expression": "__import__('os').system('echo unsafe')"},
    )
    assert unsafe.success is False
    assert unsafe.error_code == errors.ToolErrorCode.EXECUTION_ERROR
    assert "不允许" in unsafe.message
