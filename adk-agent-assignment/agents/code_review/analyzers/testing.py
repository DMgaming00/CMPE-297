"""Test-gap analysis: which public functions are untested and what to test."""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from ..models import Finding
from .ast_utils import call_name, functions


def is_test_file(filename: str, tree: ast.AST | None) -> bool:
    name = PurePosixPath(filename).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return tree is not None and any(fn.name.startswith("test_") for fn in functions(tree))


def suggest_tests(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    ideas = [f"{fn.name}: happy path with representative input"]
    params = {a.arg for a in fn.args.args if a.arg not in {"self", "cls"}}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and call_name(node) == "len" and node.args \
                and isinstance(node.args[0], ast.Name) and node.args[0].id in params:
            ideas.append(f"{fn.name}: empty {node.args[0].id}")
        if isinstance(node, ast.Raise):
            ideas.append(f"{fn.name}: error path raising {ast.unparse(node.exc or node)[:40]}")
        if isinstance(node, ast.For | ast.While):
            ideas.append(f"{fn.name}: zero, one and many iterations")
        if isinstance(node, ast.Call) and call_name(node).split(".")[-1] in {
                "execute", "get", "post", "run", "open", "urlopen"}:
            ideas.append(f"{fn.name}: mock the external call '{call_name(node)}' and its "
                         "failure")
        if isinstance(node, ast.If):
            ideas.append(f"{fn.name}: both outcomes of 'if {ast.unparse(node.test)[:40]}'")
    return list(dict.fromkeys(ideas))[:6]


def check_tests(trees: dict[str, ast.AST | None]) -> tuple[list[Finding], dict[str, list[str]]]:
    test_files = {f for f, t in trees.items() if is_test_file(f, t)}
    referenced: set[str] = set()
    asserting_tests: dict[str, bool] = {}
    for f in test_files:
        tree = trees[f]
        if tree is None:
            continue
        referenced |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        referenced |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for fn in functions(tree):
            if fn.name.startswith("test_"):
                asserting_tests[f"{f}:{fn.name}"] = any(
                    isinstance(n, ast.Assert) or (isinstance(n, ast.Call) and (
                        call_name(n).startswith(("self.assert", "pytest.raises"))))
                    for n in ast.walk(fn))
    findings: list[Finding] = []
    plan: dict[str, list[str]] = {}
    for f, tree in trees.items():
        if f in test_files or tree is None:
            continue
        public = [fn for fn in functions(tree) if not fn.name.startswith("_")]
        untested = [fn for fn in public if fn.name not in referenced]
        for fn in untested:
            plan[fn.name] = suggest_tests(fn)
        if untested:
            names = ", ".join(fn.name for fn in untested[:8])
            findings.append(Finding(
                rule_id="TST001" if not test_files else "TST002", severity="P2",
                category="testing", file=f, line=untested[0].lineno,
                title=f"{len(untested)} public function(s) without tests",
                explanation=("No test files were submitted. " if not test_files else "")
                + f"Untested: {names}.",
                recommendation="Add unit tests covering the cases in the generated test plan "
                               "(boundaries, error paths, external-call failures).",
                confidence="medium" if not test_files else "high"))
    for test_id, has_assert in asserting_tests.items():
        if not has_assert:
            file, name = test_id.split(":", 1)
            findings.append(Finding(rule_id="TST003", severity="P2", category="testing",
                                    file=file, line=1, title=f"{name} has no assertions",
                                    explanation="A test without assertions passes even when "
                                                "the code is wrong.",
                                    recommendation="Assert on the observable result."))
    return findings, plan
