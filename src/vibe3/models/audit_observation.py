"""Audit observation data models for tracking failure patterns and evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, Field


class ObservationLayer(str, Enum):
    """Affected layer in the system architecture.

    Aligns with audit-observation.md observed_failure_mode taxonomy.
    """

    RUNTIME = "runtime"
    PROMPT_RECIPE = "prompt_recipe"
    PROMPT_MATERIAL = "prompt_material"
    SKILL_CONTRACT = "skill_contract"
    GOVERNANCE_POLICY = "governance_policy"
    REPO_PROFILE = "repo_profile"
    MEMORY_SIGNAL = "memory_signal"


class ObservationSourceWindow(BaseModel):
    """Source references for an observation.

    Captures all external references needed to trace back to original evidence.
    """

    issue_number: int | None = None
    branch: str | None = None
    pr_number: int | None = None
    commit_shas: list[str] = Field(default_factory=list)
    prompt_hash: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)


class AuditObservation(BaseModel):
    """Structured observation record for audit trail.

    Aligns with audit-observation.md YAML schema and provides:
    - Unique observation ID
    - Source window with traceable references
    - Symptom and failure mode classification
    - Facts, interpretation, and next-stage input
    - Source watermark for deduplication
    """

    observation_id: str = Field(
        description="Unique identifier, e.g., 'obs-<timestamp>-<hash>'"
    )
    observation_type: str = Field(
        description="Type of observation, e.g., 'flow_failure', 'memory_signal'"
    )
    source_material: str = Field(
        default="supervisor/governance/audit-observation.md",
        description="Source governance material for this observation",
    )
    source_window: ObservationSourceWindow = Field(
        description="Source references for traceability"
    )
    flow_status: str = Field(
        default="unknown",
        description="Flow status: blocked | failed | aborted | done | unknown",
    )
    symptom: str = Field(description="What happened, stated briefly")
    observed_failure_mode: Literal[
        "scope_mismatch",
        "missing_output",
        "state_loop",
        "contract_missing",
        "ci_failure",
        "review_gap",
        "unknown",
    ] = Field(description="Classified failure mode per governance taxonomy")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level based on evidence strength"
    )
    created_by: str = Field(
        description="Creator identifier, e.g., 'governance/audit-observation', "
        "'cli/audit-observe'"
    )
    created_at: str = Field(description="ISO 8601 timestamp")
    source_watermark: str = Field(
        description="Deduplication key: hash of (branch, event_timestamps, "
        "prompt_hash, pr_number)"
    )
    facts: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of source-backed facts with kind, ref, summary",
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict,
        description="Interpretation: reasoning, likely_agent_failure, "
        "affected_material_candidates, affected_layer",
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
        description="Input for next stage: suitable_for_clustering, "
        "suggested_cluster_key, requires_human_review",
    )
    sample_count: int = Field(
        default=1, description="Number of samples in this observation"
    )
    raw_refs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional raw references for internal use",
    )

    @staticmethod
    def compute_observation_id(timestamp: str, source_watermark: str) -> str:
        """Generate unique observation ID from timestamp and watermark."""
        hash_input = f"{timestamp}-{source_watermark}".encode()
        hash_suffix = sha256(hash_input).hexdigest()[:8]
        clean_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
        return f"obs-{clean_ts}-{hash_suffix}"

    @staticmethod
    def compute_watermark(
        branch: str,
        updated_at: str | None,
        pr_number: int | None,
        prompt_hash: str | None,
    ) -> str:
        """Compute watermark hash for deduplication.

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

        watermark_input = "|".join(components).encode()
        return sha256(watermark_input).hexdigest()[:16]

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
            "unknown",
        ],
        confidence: Literal["high", "medium", "low"],
        created_by: str,
        flow_status: str = "unknown",
        facts: list[dict[str, str]] | None = None,
        interpretation: dict[str, Any] | None = None,
        limitations: list[str] | None = None,
        next_stage_input: dict[str, Any] | None = None,
        sample_count: int = 1,
        raw_refs: dict[str, Any] | None = None,
        updated_at: str | None = None,
        prompt_hash: str | None = None,
    ) -> AuditObservation:
        """Factory method to create observation with auto-generated IDs."""
        created_at = datetime.now(timezone.utc).isoformat()

        # Compute watermark from source window
        source_watermark = cls.compute_watermark(
            branch=source_window.branch or "",
            updated_at=updated_at,
            pr_number=source_window.pr_number,
            prompt_hash=prompt_hash or source_window.prompt_hash,
        )

        # Compute observation ID
        observation_id = cls.compute_observation_id(created_at, source_watermark)

        # Default interpretation structure
        default_interpretation = {
            "reasoning": "",
            "likely_agent_failure": "",
            "affected_material_candidates": [],
        }

        # Default next_stage_input structure
        default_next_stage = {
            "suitable_for_clustering": True,
            "requires_human_review": True,
        }

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
            interpretation=interpretation or default_interpretation,
            limitations=limitations or [],
            next_stage_input=next_stage_input or default_next_stage,
            sample_count=sample_count,
            raw_refs=raw_refs or {},
        )
