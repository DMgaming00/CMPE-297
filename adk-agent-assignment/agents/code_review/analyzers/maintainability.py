"""Maintainability metrics: complexity, size, nesting and documentation."""

from __future__ import annotations

import ast

from ..models import Finding
from .ast_utils import FunctionNode, functions

_DECISIONS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler,
              ast.With, ast.AsyncWith, ast.Assert, ast.comprehension, ast.match_case)


def cyclomatic_complexity(fn: FunctionNode) -> int:
    score = 1
    for node in ast.walk(fn):
        if isinstance(node, _DECISIONS):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
    return score


def _max_depth(node: ast.AST, depth: int = 0) -> int:
    nested = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
    best = depth
    for child in ast.iter_child_nodes(node):
        best = max(best, _max_depth(child, depth + 1 if isinstance(child, nested) else depth))
    return best


def check_maintainability(tree: ast.AST, filename: str) -> tuple[list[Finding], int]:
    out: list[Finding] = []
    max_cc = 0
    undocumented: list[str] = []
    for fn in functions(tree):
        cc = cyclomatic_complexity(fn)
        max_cc = max(max_cc, cc)
        length = (fn.end_lineno or fn.lineno) - fn.lineno + 1
        common = {"category": "maintainability", "file": filename, "line": fn.lineno,
                  "end_line": fn.end_lineno}
        if cc > 10:
            out.append(Finding(rule_id="MNT001", severity="P2" if cc <= 20 else "P1",
                               title=f"{fn.name}() is too complex (cyclomatic complexity {cc})",
                               explanation="High branching makes the function hard to test "
                                           "and easy to break.",
                               recommendation="Extract helpers or use a dispatch table; aim "
                                              "for complexity <= 10.", **common))
        if length > 60:
            out.append(Finding(rule_id="MNT002", severity="P3",
                               title=f"{fn.name}() is long ({length} lines)",
                               explanation="Long functions mix responsibilities.",
                               recommendation="Split into smaller, named steps.", **common))
        n_params = len(fn.args.args) + len(fn.args.kwonlyargs)
        if n_params > 6:
            out.append(Finding(rule_id="MNT003", severity="P3",
                               title=f"{fn.name}() takes {n_params} parameters",
                               explanation="Many parameters are hard to call correctly.",
                               recommendation="Group related parameters into a dataclass.",
                               **common))
        depth = _max_depth(fn)
        if depth > 4:
            out.append(Finding(rule_id="MNT004", severity="P3",
                               title=f"{fn.name}() nests {depth} levels deep",
                               explanation="Deep nesting hides the main path.",
                               recommendation="Use guard clauses / early returns.", **common))
        if not fn.name.startswith("_") and ast.get_docstring(fn) is None and length > 3:
            undocumented.append(fn.name)
    if undocumented:
        out.append(Finding(rule_id="MNT005", severity="P3", category="maintainability",
                           title=f"{len(undocumented)} public function(s) lack docstrings",
                           file=filename, line=1,
                           explanation="Missing docstrings: " + ", ".join(undocumented[:10]),
                           recommendation="Document purpose, arguments, return value and "
                                          "raised exceptions.", confidence="medium"))
    return out, max_cc
