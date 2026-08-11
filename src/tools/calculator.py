from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any

from src.tools.base import BaseTool, ToolParameter


Number = int | float


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "安全计算基础算术表达式。"
    parameters = [
        ToolParameter("expression", "string", "只包含数字和基础运算符的算术表达式。"),
    ]

    async def run(self, arguments: dict[str, Any]) -> dict[str, Number]:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("参数 expression 必须是非空字符串。")

        return {"result": evaluate_expression(expression)}


def evaluate_expression(expression: str) -> Number:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("表达式语法错误，请只输入基础算术表达式。") from exc

    return _evaluate_node(tree.body)


def _evaluate_node(node: ast.AST) -> Number:
    if isinstance(node, ast.Constant):
        return _evaluate_constant(node)

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_node(node.operand)
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError(f"不允许的一元运算：{type(node.op).__name__}")
        return operation(operand)

    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError(f"不允许的二元运算：{type(node.op).__name__}")
        if isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod) and right == 0:
            raise ValueError("不能除零。")
        return operation(left, right)

    raise ValueError(f"不允许的表达式：{type(node).__name__}")


def _evaluate_constant(node: ast.Constant) -> Number:
    value = node.value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("不允许的常量类型，只能使用数字。")
    return value


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Number, Number], Number]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Number], Number]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
