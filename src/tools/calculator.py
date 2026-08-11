from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from typing import Any

from src.tools.base import BaseTool, ToolParameter
from src.tools.errors import ToolInputError


Number = int | float
MAX_EXPRESSION_LENGTH = 512
MAX_AST_NODES = 128
MAX_AST_DEPTH = 32
MAX_PARENTHESES_DEPTH = 64
MAX_INTEGER_DIGITS = 50
MAX_ABSOLUTE_FLOAT = 1e50
MAX_EXPONENT = 100


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "安全计算基础算术表达式。"
    parameters = [
        ToolParameter("expression", "string", "只包含数字和基础运算符的算术表达式。"),
    ]

    async def run(self, arguments: dict[str, Any]) -> dict[str, Number]:
        expression = arguments.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ToolInputError("参数 expression 必须是非空字符串。")

        return {"result": evaluate_expression(expression)}


def evaluate_expression(expression: str) -> Number:
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ToolInputError(f"表达式过长，最多允许 {MAX_EXPRESSION_LENGTH} 个字符。")
    if _max_parentheses_depth(expression) > MAX_PARENTHESES_DEPTH:
        raise ToolInputError(f"表达式括号嵌套过深，最多允许 {MAX_PARENTHESES_DEPTH} 层。")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolInputError("表达式语法错误，请只输入基础算术表达式。") from exc

    _validate_ast_shape(tree)
    return _ensure_safe_number(_evaluate_node(tree.body), "计算结果")


def _evaluate_node(node: ast.AST) -> Number:
    if isinstance(node, ast.Constant):
        return _evaluate_constant(node)

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_node(node.operand)
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ToolInputError(f"不允许的一元运算：{type(node.op).__name__}")
        return _ensure_safe_number(operation(operand), "计算结果")

    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ToolInputError(f"不允许的二元运算：{type(node.op).__name__}")
        if isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod) and right == 0:
            raise ToolInputError("不能除零。")
        if isinstance(node.op, ast.Pow):
            _validate_power(left, right)
        return _ensure_safe_number(operation(left, right), "计算结果")

    raise ToolInputError(f"不允许的表达式：{type(node).__name__}")


def _evaluate_constant(node: ast.Constant) -> Number:
    value = node.value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ToolInputError("不允许的常量类型，只能使用数字。")
    return _ensure_safe_number(value, "数字")


def _validate_ast_shape(tree: ast.AST) -> None:
    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > MAX_AST_NODES:
        raise ToolInputError(f"表达式节点过多，最多允许 {MAX_AST_NODES} 个节点。")

    depth = _ast_depth(tree)
    if depth > MAX_AST_DEPTH:
        raise ToolInputError(f"表达式结构过深，最多允许 {MAX_AST_DEPTH} 层。")


def _ast_depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    if not children:
        return 1
    return 1 + max(_ast_depth(child) for child in children)


def _max_parentheses_depth(expression: str) -> int:
    current_depth = 0
    max_depth = 0
    for char in expression:
        if char == "(":
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == ")":
            current_depth = max(0, current_depth - 1)
    return max_depth


def _validate_power(base: Number, exponent: Number) -> None:
    if abs(exponent) > MAX_EXPONENT:
        raise ToolInputError(f"指数过大，绝对值最多允许 {MAX_EXPONENT}。")
    if base == 0 and exponent < 0:
        raise ToolInputError("不能对 0 使用负指数。")
    if isinstance(base, int) and isinstance(exponent, int) and abs(base) > 1 and exponent > 0:
        estimated_digits = _integer_digits(base) * exponent
        if estimated_digits > MAX_INTEGER_DIGITS:
            raise ToolInputError(f"幂运算结果过大，整数最多允许 {MAX_INTEGER_DIGITS} 位。")


def _ensure_safe_number(value: Any, label: str) -> Number:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ToolInputError(f"{label}不是可用数字。")

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToolInputError(f"{label}是非有限数字，不允许 inf 或 nan。")
        if abs(value) > MAX_ABSOLUTE_FLOAT:
            raise ToolInputError(f"{label}过大，绝对值最多允许 {MAX_ABSOLUTE_FLOAT:g}。")
        return value

    if _integer_digits(value) > MAX_INTEGER_DIGITS:
        raise ToolInputError(f"{label}过大，整数最多允许 {MAX_INTEGER_DIGITS} 位。")
    return value


def _integer_digits(value: int) -> int:
    return len(str(abs(value)))


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
