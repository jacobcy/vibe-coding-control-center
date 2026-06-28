"""Versioned evidence models for the inspect command surface."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class KernelImpact(StrEnum):
    """How deeply a change touches repository-owned review kernel files."""

    NONE = "none"
    SMALL = "small"
    LARGE = "large"


class ReviewDepth(StrEnum):
    """Minimum review policy selected from explicit repository rules."""

    NORMAL = "normal"
    FOCUSED = "focused"
    REPEATED = "repeated"


class SourceRange(BaseModel):
    """One-based inclusive source range."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Reject ranges that cannot point to real source text."""
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


class Diagnostic(BaseModel):
    """Explicit failure, skip, or limitation evidence."""

    code: str
    message: str
    path: str | None = None
    range: SourceRange | None = None


class ChangedFileFact(BaseModel):
    """Git-backed facts for one changed path."""

    path: str
    old_path: str | None = None
    status: Literal["A", "C", "D", "M", "R", "T", "U", "X", "B"]
    additions: int | None = Field(default=None, ge=0)
    deletions: int | None = Field(default=None, ge=0)
    binary: bool = False


class ChangePartitionSummary(BaseModel):
    """Counts for one Git change partition."""

    files: int = Field(default=0, ge=0)
    additions: int | None = Field(default=0, ge=0)
    deletions: int | None = Field(default=0, ge=0)


class ChangeSummary(BaseModel):
    """Partitioned summary without collapsing working-tree states."""

    committed: ChangePartitionSummary = Field(default_factory=ChangePartitionSummary)
    staged: ChangePartitionSummary = Field(default_factory=ChangePartitionSummary)
    unstaged: ChangePartitionSummary = Field(default_factory=ChangePartitionSummary)
    untracked: ChangePartitionSummary = Field(default_factory=ChangePartitionSummary)
    unique_paths: int = Field(default=0, ge=0)


class ChangeObservation(BaseModel):
    """Committed and working-tree changes kept as distinct evidence."""

    committed: list[ChangedFileFact] = Field(default_factory=list)
    staged: list[ChangedFileFact] = Field(default_factory=list)
    unstaged: list[ChangedFileFact] = Field(default_factory=list)
    untracked: list[ChangedFileFact] = Field(default_factory=list)
    summary: ChangeSummary = Field(default_factory=ChangeSummary)


class ComparisonObservation(BaseModel):
    """Exact Git revisions used for a branch comparison."""

    current_branch: str
    head_sha: str
    requested_base: str | None
    resolved_base: str
    merge_base_sha: str


class KernelHit(BaseModel):
    """One changed file matched by an explicit kernel entry."""

    path: str
    responsibilities: list[str] = Field(min_length=1)
    reason: str
    review_floor: ReviewDepth
    sources: list[str] = Field(min_length=1)


class KernelObservation(BaseModel):
    """Deterministic Review/Architecture Kernel classification."""

    status: Literal["ready", "unavailable"] = "ready"
    impact: KernelImpact
    architecture_hits: list[KernelHit] = Field(default_factory=list)
    review_hits: list[KernelHit] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ReviewPolicy(BaseModel):
    """Repository-owned minimum review policy, not a risk prediction."""

    minimum_depth: ReviewDepth
    reasons: list[str] = Field(default_factory=list)


class ImpactAnalysisStatus(BaseModel):
    """Honest product boundary for the failed impact-analysis benchmark."""

    status: Literal["disabled"] = "disabled"
    reason: Literal["benchmark_gate_failed"] = "benchmark_gate_failed"


class ReviewObservation(BaseModel):
    """Versioned inspect-base result shared by command and PR consumers."""

    schema_version: Literal[1] = 1
    status: Literal["ready", "partial", "error"]
    comparison: ComparisonObservation | None = None
    changes: ChangeObservation = Field(default_factory=ChangeObservation)
    kernel: KernelObservation | None = None
    review: ReviewPolicy | None = None
    impact_analysis: ImpactAnalysisStatus = Field(default_factory=ImpactAnalysisStatus)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
