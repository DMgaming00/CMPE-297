"""AST rules for likely bugs (correctness)."""

from __future__ import annotations

import ast

from ..models import Finding
from .ast_utils import FunctionNode, call_name, functions, names_in

_BUILTINS = {"list", "dict", "str", "id", "type", "input", "sum", "max", "min", "filter",
             "map", "len", "set", "object", "format", "hash", "iter", "next", "file"}
_MUTATORS = {"append", "remove", "pop", "insert", "extend", "clear", "add", "discard"}


def _finding(filename: str, node: ast.AST, rule: str, severity: str, title: str,
             explanation: str, recommendation: str, confidence: str = "high",
             category: str = "correctness") -> Finding:
    return Finding(rule_id=rule, title=title, severity=severity, category=category,
                   file=filename, line=getattr(node, "lineno", 1),
                   end_line=getattr(node, "end_lineno", None), explanation=explanation,
                   recommendation=recommendation, confidence=confidence)


def _guarded_names(fn: FunctionNode) -> set[str]:
    """Names that appear in an if/while/assert/ternary test inside the function."""
    guarded: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.If | ast.While | ast.IfExp | ast.Assert):
            guarded |= names_in(node.test)
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is not None and "ZeroDivisionError" in ast.unparse(handler.type):
                    guarded |= names_in(node)
    return guarded


def check_correctness(tree: ast.AST, filename: str) -> list[Finding]:
    out: list[Finding] = []
    add = out.append

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                add(_finding(filename, node, "COR001", "P2", "Bare except clause",
                             "Catches SystemExit/KeyboardInterrupt and hides real errors.",
                             "Catch the specific exceptions you expect (e.g. except ValueError)."))
            elif ast.unparse(node.type) in {"Exception", "BaseException"} and all(
                    isinstance(s, ast.Pass | ast.Continue) for s in node.body):
                add(_finding(filename, node, "COR002", "P2", "Exception silently swallowed",
                             "Errors disappear without logging, making failures invisible.",
                             "Log the exception or handle a specific error type."))
        elif isinstance(node, ast.Compare):
            for op, right in zip(node.ops, node.comparators, strict=False):
                if isinstance(op, ast.Eq | ast.NotEq) and isinstance(right, ast.Constant) \
                        and right.value is None:
                    add(_finding(filename, node, "COR004", "P3", "Comparison to None with ==",
                                 "== None can be overridden by __eq__; identity is intended.",
                                 "Use 'is None' / 'is not None'.", category="style"))
                if isinstance(op, ast.Is | ast.IsNot) and isinstance(right, ast.Constant) \
                        and right.value not in (None, True, False, ...):
                    add(_finding(filename, node, "COR005", "P1", "Identity comparison with a "
                                 "literal", "'is' compares object identity; results for "
                                 "strings/ints depend on interning and are unreliable.",
                                 "Use == for value comparison."))
        elif isinstance(node, ast.Dict):
            seen: set[object] = set()
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    if key.value in seen:
                        add(_finding(filename, key, "COR008", "P2", "Duplicate dictionary key",
                                     f"Key {key.value!r} appears twice; the first value is "
                                     "silently overwritten.", "Remove or rename the duplicate."))
                    seen.add(key.value)
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr in _MUTATORS and isinstance(sub.func.value, ast.Name) \
                        and sub.func.value.id == node.iter.id:
                    add(_finding(filename, sub, "COR014", "P1",
                                 f"'{node.iter.id}' modified while iterating over it",
                                 "Mutating a list during iteration skips or repeats elements.",
                                 f"Iterate over a copy (for x in list({node.iter.id})) or build "
                                 "a new list with a comprehension."))
                    break
        elif isinstance(node, ast.Try) and node.finalbody:
            for sub in node.finalbody:
                if isinstance(sub, ast.Return):
                    add(_finding(filename, sub, "COR016", "P2", "return inside finally",
                                 "A return in finally discards any in-flight exception.",
                                 "Move the return out of the finally block."))
        elif isinstance(node, ast.Call) and call_name(node) == "open":
            parent_is_with = getattr(node, "_in_with", False)
            if not parent_is_with:
                add(_finding(filename, node, "COR009", "P3", "File opened without a context "
                             "manager", "The handle may leak if an exception occurs before "
                             "close().", "Use 'with open(...) as f:'.", "medium",
                             category="maintainability"))
        for body_name in ("body", "orelse", "finalbody"):
            block = getattr(node, body_name, None)
            if isinstance(block, list):
                for i, stmt in enumerate(block[:-1]):
                    if isinstance(stmt, ast.Return | ast.Raise | ast.Break | ast.Continue):
                        add(_finding(filename, block[i + 1], "COR007", "P2", "Unreachable code",
                                     "Statements after return/raise/break/continue never run.",
                                     "Delete the dead code or fix the control flow."))
                        break

    for fn in functions(tree):
        guarded = _guarded_names(fn)
        defaults = fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]
        for default in defaults:
            mutable = isinstance(default, ast.List | ast.Dict | ast.Set) or (
                isinstance(default, ast.Call) and call_name(default) in {"list", "dict", "set"})
            if mutable:
                add(_finding(filename, default, "COR003", "P2", f"Mutable default argument in "
                             f"{fn.name}()", "The default object is shared across calls, so "
                             "state leaks between invocations.",
                             "Default to None and create the object inside the function."))
        for arg in fn.args.args + fn.args.kwonlyargs:
            if arg.arg in _BUILTINS:
                add(_finding(filename, arg, "COR010", "P3", f"Parameter shadows builtin "
                             f"'{arg.arg}'", "Shadowing builtins causes confusing bugs when "
                             "the builtin is needed later.", "Rename the parameter.",
                             category="maintainability"))
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.FloorDiv
                                                          | ast.Mod) \
                    and isinstance(node.right, ast.Call) and call_name(node.right) == "len" \
                    and node.right.args and isinstance(node.right.args[0], ast.Name) \
                    and node.right.args[0].id not in guarded:
                seq = node.right.args[0].id
                add(_finding(filename, node, "COR006", "P1", f"ZeroDivisionError when "
                             f"'{seq}' is empty", f"{fn.name}() divides by len({seq}) without "
                             f"checking that {seq} is non-empty.",
                             f"Guard the empty case explicitly (e.g. 'if not {seq}: raise "
                             "ValueError(...)' or return a documented default) and add a test."))
    return out


def mark_with_items(tree: ast.AST) -> None:
    """Annotate open() calls used as context managers (so COR009 skips them)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    item.context_expr._in_with = True  # type: ignore[attr-defined]
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            node.value._in_with = True  # returning the handle transfers ownership
