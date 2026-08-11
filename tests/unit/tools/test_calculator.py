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
@pytest.mark.parametrize(
    ("expression", "expected_message"),
    [
        ("2 ** 100000000", "指数"),
        ("1e309", "非有限"),
        ("1+" * 300 + "1", "过长"),
        ("-" * 40 + "1", "过深"),
        (" + ".join(["1"] * 100), "过多"),
    ],
)
async def test_calculator_rejects_resource_exhaustion_inputs(
    expression: str,
    expected_message: str,
):
    calculator = _calculator_module().CalculatorTool()

    with pytest.raises(ValueError) as exc_info:
        await calculator.run({"expression": expression})

    assert expected_message in str(exc_info.value)


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
    assert unsafe.error_code == errors.ToolErrorCode.INVALID_ARGUMENTS
    assert "不允许" in unsafe.message


@pytest.mark.asyncio
async def test_invalid_calculator_inputs_do_not_trip_circuit_breaker():
    errors, registry = _registry_modules()
    registry_obj = registry.ToolRegistry(failure_threshold=3)
    registry_obj.register(_calculator_module().CalculatorTool())

    for _ in range(3):
        invalid = await registry_obj.invoke("calculator", {"expression": "1 / 0"})
        assert invalid.success is False
        assert invalid.error_code == errors.ToolErrorCode.INVALID_ARGUMENTS
        assert "除零" in invalid.message

    valid = await registry_obj.invoke("calculator", {"expression": "2 + 2"})

    assert valid.success is True
    assert valid.data == {"result": 4}


@pytest.mark.asyncio
async def test_float_power_overflow_is_invalid_arguments_and_does_not_trip_circuit_breaker():
    errors, registry = _registry_modules()
    registry_obj = registry.ToolRegistry(failure_threshold=3)
    registry_obj.register(_calculator_module().CalculatorTool())

    for _ in range(3):
        overflow = await registry_obj.invoke("calculator", {"expression": "1e50 ** 100"})
        assert overflow.success is False
        assert overflow.error_code == errors.ToolErrorCode.INVALID_ARGUMENTS
        assert "过大" in overflow.message or "溢出" in overflow.message

    valid = await registry_obj.invoke("calculator", {"expression": "3 * 3"})

    assert valid.success is True
    assert valid.data == {"result": 9}
