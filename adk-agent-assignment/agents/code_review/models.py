"""Schemas shared by the deterministic analyzers and the LLM specialist reviewers.

Severity model
  P0  critical / blocker  - exploitable vulnerability, data loss, crash on main path
  P1  high                - likely bug or security weakness; fix before merge
  P2  medium              - real defect risk or missing tests; fix soon
  P3  low / informational - maintainability and style
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["P0", "P1", "P2", "P3"]
Category = Literal["correctness", "security", "testing", "maintainability", "style",
                   "performance"]
Confidence = Literal["high", "medium", "low"]
Verdict = Literal["APPROVE", "COMMENT", "REQUEST_CHANGES"]
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class Finding(BaseModel):
    id: str = Field(default="", description="Stable id: RULE:file:line (static findings).")
    rule_id: str
    title: str
    severity: Severity
    category: Category
    file: str
    line: int = Field(ge=1)
    end_line: int | None = None
    explanation: str
    recommendation: str
    confidence: Confidence = "high"
    source: Literal["static", "llm"] = "static"

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = f"{self.rule_id}:{self.file}:{self.line}"


class SpecialistFinding(BaseModel):
    """A finding proposed by an LLM specialist (validated before it is reported)."""

    title: str = Field(description="One-line summary of the defect.")
    severity: Severity
    category: Category
    file: str = Field(description="File name exactly as shown in the code listing.")
    line: int = Field(ge=1, description="Line number from the code listing.")
    evidence: str = Field(description="The exact code snippet (copied) that shows the issue.")
    explanation: str = Field(description="Why this is a problem and its impact.")
    recommendation: str = Field(description="Concrete fix, ideally with corrected code.")
    confidence: Confidence


class SpecialistReview(BaseModel):
    summary: str = Field(description="Two or three sentences from this specialist.")
    findings: list[SpecialistFinding] = Field(default_factory=list)
    rejected_static_finding_ids: list[str] = Field(
        default_factory=list,
        description="Ids of static-analysis findings that are false positives in context.")


class FileMetrics(BaseModel):
    file: str
    lines: int
    functions: int
    classes: int
    max_complexity: int
    style_violations: int
    style_score: int
    parse_error: str | None = None


class StaticReport(BaseModel):
    findings: list[Finding]
    metrics: list[FileMetrics]
    test_plan: dict[str, list[str]] = Field(default_factory=dict)
