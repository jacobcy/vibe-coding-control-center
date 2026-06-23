"""Audit observation data models for tracking failure patterns and evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, Field


class ObservationSourceWindow(BaseModel):
    """Source references for traceability.

    Captures all external references needed to trace back to original evidence.
    """

    issue_number: int | None = None
    branch: str | None = None
    pr_number: int | None = None
    commit_shas: list[str] = Field(default_factory=list)
    prompt_hash: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(
        default_factory=list,
        description="Generic memory plugin references (NOT claude-mem specific)",
    )


class AuditObservation(BaseModel):
    """Structured observation record for audit trail.

    Aligns with .vibe/governance/audit-observation.md YAML schema.
    Provides stable interface for observation collection and analysis.
    """

    # === Identity ===
    observation_id: str = Field(description="Unique identifier: obs-<timestamp>-<hash>")
    observation_type: str = Field(
        description="Type: flow_blocked | execution_crashed | memory_signal | ..."
    )
    source_material: str = Field(
        default=".vibe/governance/audit-observation.md",
        description="Source governance material for this observation",
    )

    # === Subject ===
    source_window: ObservationSourceWindow = Field(
        description="Source references for traceability"
    )
    flow_status: str = Field(
        default="unknown",
        description="Flow status: blocked | failed | aborted | done | unknown",
    )

    # === Core Observation ===
    symptom: str = Field(description="What happened, stated briefly")
    observed_failure_mode: Literal[
        "scope_mismatch",
        "missing_output",
        "state_loop",
        "contract_missing",
        "ci_failure",
        "review_gap",
        "memory_signal",
        "unknown",
    ] = Field(description="Classified failure mode per governance taxonomy")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level based on evidence strength"
    )

    # === Structured Evidence ===
    facts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Source-backed facts with kind, ref, summary",
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent reasoning: reasoning, likely_agent_failure, materials",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Missing data, stale source, or other limitations",
    )
    next_stage_input: dict[str, Any] = Field(
        default_factory=lambda: {
            "suitable_for_clustering": True,
            "requires_human_review": True,
        },
        description="Input for next stage: clustering hints, review requirements",
    )

    # === Metadata ===
    created_by: str = Field(
        description="Creator: governance/audit-observation | cli/..."
    )
    created_at: str = Field(description="ISO 8601 timestamp")
    source_watermark: str = Field(
        description="Deduplication key: hash(branch, updated_at, pr, prompt_hash)"
    )

    @staticmethod
    def compute_watermark(
        branch: str,
        updated_at: str | None,
        pr_number: int | None,
        prompt_hash: str | None,
    ) -> str:
        """Compute deduplication hash.

        Watermark is based on:
        - branch name
        - last updated timestamp
        - PR number (if any)
        - prompt hash (if any)
        """
        components = [branch]
        if updated_at:
            components.append(updated_at)
        if pr_number:
            components.append(str(pr_number))
        if prompt_hash:
            components.append(prompt_hash)
        return sha256("|".join(components).encode()).hexdigest()[:16]

    @staticmethod
    def compute_observation_id(timestamp: str, watermark: str) -> str:
        """Generate unique observation ID."""
        clean_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
        hash_suffix = sha256(f"{timestamp}-{watermark}".encode()).hexdigest()[:8]
        return f"obs-{clean_ts}-{hash_suffix}"

    @classmethod
    def create(
        cls,
        observation_type: str,
        source_window: ObservationSourceWindow,
        symptom: str,
        observed_failure_mode: Literal[
            "scope_mismatch",
            "missing_output",
            "state_loop",
            "contract_missing",
            "ci_failure",
            "review_gap",
            "memory_signal",
            "unknown",
        ],
        confidence: Literal["high", "medium", "low"],
        created_by: str,
        flow_status: str = "unknown",
        facts: list[dict[str, str]] | None = None,
        interpretation: dict[str, Any] | None = None,
        limitations: list[str] | None = None,
        next_stage_input: dict[str, Any] | None = None,
        updated_at: str | None = None,
        prompt_hash: str | None = None,
    ) -> AuditObservation:
        """Factory method to create observation with auto-generated IDs."""
        created_at = datetime.now(timezone.utc).isoformat()

        # Compute watermark
        source_watermark = cls.compute_watermark(
            branch=source_window.branch or "",
            updated_at=updated_at,
            pr_number=source_window.pr_number,
            prompt_hash=prompt_hash or source_window.prompt_hash,
        )

        # Compute observation ID
        observation_id = cls.compute_observation_id(created_at, source_watermark)

        return cls(
            observation_id=observation_id,
            observation_type=observation_type,
            source_window=source_window,
            flow_status=flow_status,
            symptom=symptom,
            observed_failure_mode=observed_failure_mode,
            confidence=confidence,
            created_by=created_by,
            created_at=created_at,
            source_watermark=source_watermark,
            facts=facts or [],
            interpretation=interpretation or {},
            limitations=limitations or [],
            next_stage_input=next_stage_input
            or {
                "suitable_for_clustering": True,
                "requires_human_review": True,
            },
        )
