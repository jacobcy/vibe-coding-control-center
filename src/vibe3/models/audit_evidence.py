"""Audit evidence data models.

Implements the schema defined in docs/standards/v3/audit-evidence-model-standard.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Source reference models (§4)


class GitHubRef(BaseModel):
    """GitHub source reference (issue, PR, comment, review, label)."""

    kind: Literal["issue", "issue_comment", "pr", "pr_comment", "review", "label"]
    number: int
    url: str
    author: str | None = None
    created_at: str | None = Field(default=None, description="ISO 8601 timestamp")
    marker: str | None = None


class FlowRef(BaseModel):
    """Flow store reference (flow state, timeline events, issue links)."""

    branch: str
    flow_slug: str | None = None
    event_id: int | None = None
    event_type: str | None = None
    actor: str | None = None
    created_at: str | None = Field(default=None, description="ISO 8601 timestamp")
    watermark: str = Field(
        ...,
        description="Hash that changes when flow receives new events/refs/PR updates",
    )


class HandoffRef(BaseModel):
    """Handoff artifact reference (plan, report, audit, indicate, verdict, current)."""

    branch: str
    kind: Literal["plan", "report", "audit", "indicate", "verdict", "current", "other"]
    artifact_ref: str
    actor: str | None = None
    created_at: str | None = Field(default=None, description="ISO 8601 timestamp")


class GitRef(BaseModel):
    """Git commit, diff range, branch, or tag reference."""

    kind: Literal["commit", "diff_range", "branch", "tag"]
    ref: str
    base_ref: str | None = None
    head_ref: str | None = None
    author: str | None = None
    committed_at: str | None = Field(default=None, description="ISO 8601 timestamp")
    files_changed: list[str] = Field(default_factory=list)


class PromptRef(BaseModel):
    """Rendered prompt reference (dry-run/render provenance)."""

    recipe_key: str
    variant: str | None = None
    rendered_hash: str
    rendered_at: str | None = Field(default=None, description="ISO 8601 timestamp")
    sections: list[dict[str, str | int | None]] = Field(
        default_factory=list,
        description="List of {key, source_kind, source_ref, size_chars}",
    )


class SkillRef(BaseModel):
    """Skill invocation reference."""

    name: str
    path: str
    version_ref: str | None = None
    invoked_for: dict[str, int | str | None] = Field(
        default_factory=dict,
        description="{issue_number, branch} context",
    )
    output_refs: list[str] = Field(default_factory=list)


class MemoryRef(BaseModel):
    """Claude-memory observation reference (auxiliary source)."""

    provider: Literal["claude-mem"]
    query: str
    memory_ids: list[str] = Field(default_factory=list)
    project: str | None = None
    platform: str | None = None
    observed_at: str | None = Field(default=None, description="ISO 8601 timestamp")
    staleness: Literal["fresh", "stale", "unknown"] = "unknown"


# Aggregate containers


class SourceRefs(BaseModel):
    """Container for all source reference types."""

    github: list[GitHubRef] = Field(default_factory=list)
    flow: list[FlowRef] = Field(default_factory=list)
    handoff: list[HandoffRef] = Field(default_factory=list)
    git: list[GitRef] = Field(default_factory=list)
    prompt: list[PromptRef] = Field(default_factory=list)
    skill: list[SkillRef] = Field(default_factory=list)
    memory: list[MemoryRef] = Field(default_factory=list)


class TimeWindow(BaseModel):
    """Time window for evidence collection."""

    start: str | None = Field(default=None, description="ISO 8601 start timestamp")
    end: str | None = Field(default=None, description="ISO 8601 end timestamp")


class RepoInfo(BaseModel):
    """Repository identity."""

    owner: str
    name: str
    local_root: str | None = None


class CollectionContext(BaseModel):
    """Metadata about evidence collection process."""

    mode: Literal["issue", "flow", "pr", "time_window", "manual"]
    source_machine: str | None = None
    source_db: str | None = None
    source_commit: str | None = None
    time_window: TimeWindow = Field(default_factory=TimeWindow)


class PrimarySubject(BaseModel):
    """Primary subject of the audit (issue, branch, or PR)."""

    issue_number: int | None = None
    branch: str | None = None
    pr_number: int | None = None


class Trust(BaseModel):
    """Trust classification for evidence sources."""

    source_class: Literal["authoritative", "derived", "auxiliary"]
    freshness: Literal["fresh", "stale", "unknown"]
    confidence: Literal["strong", "medium", "weak", "inconclusive"]
    limitations: list[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    """Human-readable summary of evidence."""

    symptom: str = Field(..., description="Observed symptom or anomaly")
    evidence_text: str = Field(
        ..., description="Bounded text summary, not full raw artifacts"
    )
    candidate_failure_patterns: list[str] = Field(default_factory=list)


# Top-level container


class EvidenceBundle(BaseModel):
    """Top-level evidence bundle for audit input.

    This is the bounded input object produced before observation.
    It must be small enough for audit agents to inspect without
    reading every linked raw artifact.
    """

    id: str
    schema_version: int = Field(
        default=1, description="Schema version for compatibility"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO 8601 timestamp",
    )
    created_by: str
    repo: RepoInfo
    collection_context: CollectionContext
    primary_subject: PrimarySubject
    source_refs: SourceRefs = Field(default_factory=SourceRefs)
    summary: EvidenceSummary
    trust: Trust
