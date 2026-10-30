"""Small AST helpers shared by the rule modules."""

from __future__ import annotations

import ast
from collections.abc import Iterator

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def dotted_name(node: ast.AST) -> str:
    """Return 'a.b.c' for Name/Attribute chains (empty string otherwise)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):
        inner = dotted_name(node.func)
        return ".".join([inner + "()", *reversed(parts)]) if inner else ""
    return ""


def call_name(node: ast.Call) -> str:
    return dotted_name(node.func)


def keyword(node: ast.Call, name: str) -> ast.expr | None:
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def is_true(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def is_false(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def is_dynamic_string(node: ast.AST) -> bool:
    """f-strings with placeholders, '%' formatting, '+' concatenation or .format()."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        return _has_str(node.left) or _has_str(node.right) or is_dynamic_string(node.left)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format" and _has_str(node.func.value)
    return False


def _has_str(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) for n in ast.walk(node)
               ) or isinstance(node, ast.JoinedStr)


def string_text(node: ast.AST) -> str:
    return " ".join(n.value for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str))


def functions(tree: ast.AST) -> Iterator[FunctionNode]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
