"""The deterministic analyzers must catch every planted defect in the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from adk_shared.config import DATA_DIR
from agents.code_review.analyzers import analyze_files, render_listing
from agents.code_review.analyzers.maintainability import cyclomatic_complexity

FIXTURES = DATA_DIR / "code_review"


def _analyze(*names: str):
    return analyze_files({n: (FIXTURES / n).read_text() for n in names})


def _rules(report) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for f in report.findings:
        out.setdefault(f.rule_id, set()).add(f.line)
    return out


def test_vulnerable_fixture_detects_all_planted_security_defects():
    report = _analyze("vulnerable_app.py")
    rules = _rules(report)
    expected = {"SEC001": "eval", "SEC002": "command injection", "SEC003": "SQL injection",
                "SEC004": "pickle", "SEC005": "yaml", "SEC006": "hard-coded secret",
                "SEC007": "TLS verify", "SEC008": "md5 password", "SEC010": "debug",
                "SEC012": "path traversal", "SEC013": "SSRF"}
    missing = {rule: label for rule, label in expected.items() if rule not in rules}
    assert not missing, f"missed planted defects: {missing}"
    severities = {f.rule_id: f.severity for f in report.findings}
    assert severities["SEC003"] == "P0" and severities["SEC002"] == "P0"
    assert severities["SEC001"] == "P0"


def test_buggy_fixture_detects_correctness_defects():
    rules = _rules(_analyze("buggy_inventory.py"))
    for rule in ("COR001", "COR003", "COR004", "COR005", "COR006", "COR007", "COR008",
                 "COR014"):
        assert rule in rules, rule
    assert not any(r.startswith("SEC") for r in rules), "no false security findings"


def test_clean_fixture_with_tests_has_no_findings():
    report = _analyze("clean_module.py", "test_clean_module.py")
    assert report.findings == []


def test_classic_average_bug():
    report = analyze_files({"avg.py": "def average(xs):\n    return sum(xs) / len(xs)\n"})
    zero_div = [f for f in report.findings if f.rule_id == "COR006"]
    assert zero_div and zero_div[0].severity == "P1" and zero_div[0].line == 2
    assert report.test_plan["average"]


def test_guarded_division_is_not_flagged():
    code = "def average(xs):\n    if not xs:\n        return 0.0\n    return sum(xs) / len(xs)\n"
    assert not [f for f in analyze_files({"a.py": code}).findings if f.rule_id == "COR006"]


def test_parameterised_sql_and_safe_subprocess_are_not_flagged():
    code = (
        "import subprocess\n\n\n"
        "def q(conn, name):\n"
        "    conn.execute('SELECT * FROM users WHERE name = ?', (name,))\n"
        "    subprocess.run(['ls', '-l', name], check=True)\n"
    )
    report = analyze_files({"safe.py": code})
    assert not [f for f in report.findings if f.category == "security"]


def test_sql_built_in_variable_is_flagged():
    code = ("def q(cur, uid):\n    sql = 'DELETE FROM t WHERE id = %s' % uid\n"
            "    cur.execute(sql)\n")
    assert "SEC003" in _rules(analyze_files({"q.py": code}))


def test_token_literal_is_p0():
    fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"  # built at runtime so this file has no literal key
    report = analyze_files({"cfg.py": f"KEY = {fake_key!r}\n"})
    assert any(f.rule_id == "SEC006" and f.severity == "P0" for f in report.findings)


def test_syntax_error_is_reported_not_raised():
    report = analyze_files({"broken.py": "def nope(:\n    pass\n"})
    assert report.findings[0].rule_id == "COR000" and report.findings[0].severity == "P0"
    assert report.metrics[0].parse_error


def test_reviewed_code_is_never_executed(tmp_path: Path):
    marker = tmp_path / "pwned"
    code = f"open({str(marker)!r}, 'w').write('x')\nimport os\nos.system('touch {marker}')\n"
    analyze_files({"evil.py": code})
    assert not marker.exists()


@pytest.mark.parametrize("code,expected", [
    ("def f(x):\n    return x\n", 1),
    ("def f(x):\n    if x and x > 1:\n        return 1\n    for i in x:\n        pass\n", 4),
])
def test_cyclomatic_complexity(code, expected):
    import ast

    fn = ast.parse(code).body[0]
    assert cyclomatic_complexity(fn) == expected


def test_listing_has_line_numbers():
    listing = render_listing({"a.py": "x = 1\ny = 2\n"})
    assert "=== FILE: a.py ===" in listing and "   2 | y = 2" in listing
