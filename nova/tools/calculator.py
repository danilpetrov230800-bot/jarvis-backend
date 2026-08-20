from __future__ import annotations

import ast
import operator
from typing import Any

from nova.tools.base import ToolResult

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    raise ValueError("unsupported")


def safe_calc(expr: str) -> str:
    cleaned = expr.replace(",", ".").strip()
    tree = ast.parse(cleaned, mode="eval")
    value = _eval(tree)
    if value == int(value):
        return str(int(value))
    return str(round(value, 8))


async def calculator(expr: str = "", **_: Any) -> ToolResult:
    if not expr:
        return ToolResult(False, "Нужно выражение, например 24*7.")
    try:
        value = safe_calc(expr)
    except Exception:
        return ToolResult(False, "Могу считать только числа и + - * /.")
    return ToolResult(True, f"Получается {value}.", {"value": value})
