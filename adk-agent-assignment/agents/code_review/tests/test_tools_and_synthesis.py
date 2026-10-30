from __future__ import annotations

from types import SimpleNamespace

from agents.code_review.analyzers import analyze_files
from agents.code_review.models import SpecialistFinding, SpecialistReview
from agents.code_review.stages import synthesize, validate_specialist_findings, verdict_for
from agents.code_review.tools import (
    load_workspace_files,
    submit_code_for_review,
    submit_fixed_code,
)


def _ctx(state=None):
    return SimpleNamespace(state=state if state is not None else {})


def test_submit_code_validates_filename_and_size():
    ctx = _ctx()
    assert submit_code_for_review("x = 1\n", "ok.py", ctx)["ok"]
    assert not submit_code_for_review("x = 1\n", "../etc/passwd.py", ctx)["ok"]
    assert not submit_code_for_review("x = 1\n", "notes.txt", ctx)["ok"]
    assert not submit_code_for_review("x" * 300_000, "big.py", ctx)["ok"]
    assert list(ctx.state["review_files"]) == ["ok.py"]


def test_workspace_loading_blocks_path_traversal(tmp_path, monkeypatch):
    (tmp_path / "inside.py").write_text("x = 1\n")
    outside = tmp_path.parent / "outside_secret.py"
    outside.write_text("SECRET = 1\n")
    (tmp_path / "link.py").symlink_to(outside)
    monkeypatch.setenv("REVIEW_WORKSPACE_ROOT", str(tmp_path))
    ctx = _ctx()
    result = load_workspace_files(["inside.py", "../outside_secret.py", "/etc/hosts.py",
                                   "link.py"], ctx)
    assert result["loaded"] == ["inside.py"]
    assert len(result["errors"]) == 3
    assert "SECRET" not in str(ctx.state["review_files"])


def test_fix_submission_must_target_reviewed_file():
    ctx = _ctx({"review_files": {"a.py": "x = 1\n"}})
    assert submit_fixed_code("a.py", "x = 2\n", ctx)["ok"]
    assert not submit_fixed_code("b.py", "x = 2\n", ctx)["ok"]


FILES = {"app.py": "import os\n\n\ndef run(cmd):\n    os.system(cmd)\n\n\ndef ok():\n"
                   "    return 1\n"}


def _state_with(reviews: dict) -> dict:
    report = analyze_files(FILES)
    return {"review_files": FILES, "static_report": report.model_dump(), **reviews}


def test_hallucinated_llm_findings_are_dropped():
    review = SpecialistReview(summary="s", findings=[
        SpecialistFinding(title="real", severity="P2", category="correctness", file="app.py",
                          line=9, evidence="return 1", explanation="e", recommendation="r",
                          confidence="high"),
        SpecialistFinding(title="wrong line", severity="P1", category="correctness",
                          file="app.py", line=999, evidence="x", explanation="e",
                          recommendation="r", confidence="high"),
        SpecialistFinding(title="invented code", severity="P0", category="security",
                          file="app.py", line=2, evidence="pickle.loads(data)",
                          explanation="e", recommendation="r", confidence="high"),
        SpecialistFinding(title="missing file", severity="P1", category="security",
                          file="ghost.py", line=1, evidence="x", explanation="e",
                          recommendation="r", confidence="high"),
    ])
    accepted, dropped = validate_specialist_findings(review, FILES)
    assert [f.title for f in accepted] == ["real"]
    assert len(dropped) == 3


def test_model_cannot_remove_high_confidence_p0_static_finding():
    static_id = next(f.id for f in analyze_files(FILES).findings if f.rule_id == "SEC002")
    state = _state_with({"security_review": SpecialistReview(
        summary="s", rejected_static_finding_ids=[static_id]).model_dump()})
    result = synthesize(state)
    assert result["verdict"] == "REQUEST_CHANGES"
    assert static_id in result["disputed"]
    assert any(f["id"] == static_id for f in result["findings"])


def test_low_severity_static_finding_can_be_rejected_by_matching_specialist():
    code = {"m.py": "def f(a, b, c, d, e, f2, g):\n    return a\n"}
    report = analyze_files(code)
    mnt = next(f for f in report.findings if f.rule_id == "MNT003")
    state = {"review_files": code, "static_report": report.model_dump(),
             "maintainability_review": SpecialistReview(
                 summary="s", rejected_static_finding_ids=[mnt.id]).model_dump(),
             "security_review": SpecialistReview(  # wrong specialty: ignored
                 summary="s", rejected_static_finding_ids=["TST001:m.py:1"]).model_dump()}
    result = synthesize(state)
    ids = {f["id"] for f in result["findings"]}
    assert mnt.id not in ids and "TST001:m.py:1" in ids


def test_malformed_specialist_output_is_ignored():
    result = synthesize(_state_with({"testing_review": {"findings": "not-a-list"}}))
    assert any("malformed" in d for d in result["dropped_llm_or_rejected"])


def test_verdict_rules():
    findings = analyze_files({"c.py": "def f():\n    return 1\n"}).findings
    assert verdict_for([]) == "APPROVE"
    assert verdict_for(findings) == "COMMENT"  # untested public function (P2)
