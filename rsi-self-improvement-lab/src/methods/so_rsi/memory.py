"""Inquiry memory: persistent causal evidence accumulated across RSI rounds."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InquiryRecord:
    episode: int
    anomaly: str  # recurrence | opposing_edits | expectation_mismatch
    subject: str  # e.g. the edit kind involved
    probe: str
    verdict: str  # the diagnosed mechanism
    intervention: str  # the structural change applied to the improver
    probe_cost: float


@dataclass
class InquiryMemory:
    records: list[InquiryRecord] = field(default_factory=list)

    def lookup(self, anomaly: str, subject: str) -> InquiryRecord | None:
        for rec in reversed(self.records):
            if rec.anomaly == anomaly and rec.subject == subject:
                return rec
        return None

    def add(self, rec: InquiryRecord) -> None:
        self.records.append(rec)

    def to_list(self) -> list[dict[str, Any]]:
        return [asdict(r) for r in self.records]
