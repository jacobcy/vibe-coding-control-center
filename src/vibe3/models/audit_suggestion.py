"""Audit suggestion data model for structured improvement suggestions.

This module defines the Pydantic model for audit suggestions, which represent
actionable hypotheses derived from observation clusters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field


class AuditSuggestion(BaseModel):
    """Structured suggestion record for audit improvements.

    Suggestions are derived from observation clusters, following the layered
    audit evidence model (ADR-0005): raw → observation → suggestion → decision.
    """

    # === Identity ===
    suggestion_id: str = Field(description="Unique identifier: sug-<timestamp>-<hash>")
    linked_observation_ids: list[str] = Field(
        default_factory=list,
        description="Observation YAML filenames or observation_ids",
    )

    # === Hypothesis ===
    hypothesis: str = Field(
        description="The core hypothesis explaining the observation cluster"
    )
    affected_layer: Literal[
        "runtime",
        "prompt_recipe",
        "prompt_material",
        "skill_contract",
        "governance_policy",
        "repo_profile",
        "memory_signal",
    ] = Field(description="Which layer is affected by this suggestion")
    target_refs: list[str] = Field(
        default_factory=list,
        description="Paths, section keys, recipe/skill/policy names",
    )

    # === Action ===
    recommended_action: Literal[
        "no_action",
        "create_followup",
        "bounded_edit",
        "evaluate_more",
    ] = Field(description="Recommended action type")

    # === Expected Outcome ===
    expected_metric: str = Field(description="What metric should change")
    expected_trend: str = Field(description="increase / decrease / stabilize")

    # === Confidence & Risk ===
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level based on evidence strength"
    )
    regression_risk: Literal["high", "medium", "low"] = Field(
        description="Risk of regression if action is taken"
    )

    # === Metadata ===
    created_by: str = Field(
        default="governance/audit-suggestion", description="Creator identifier"
    )
    created_at: str = Field(description="ISO 8601 timestamp")

    @staticmethod
    def compute_suggestion_id(timestamp: str, hypothesis_hash: str) -> str:
        """Generate unique suggestion ID."""
        clean_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
        hash_suffix = sha256(f"{timestamp}-{hypothesis_hash}".encode()).hexdigest()[:8]
        return f"sug-{clean_ts}-{hash_suffix}"

    @classmethod
    def create(
        cls,
        hypothesis: str,
        linked_observation_ids: list[str],
        affected_layer: Literal[
            "runtime",
            "prompt_recipe",
            "prompt_material",
            "skill_contract",
            "governance_policy",
            "repo_profile",
            "memory_signal",
        ],
        target_refs: list[str],
        recommended_action: Literal[
            "no_action",
            "create_followup",
            "bounded_edit",
            "evaluate_more",
        ],
        expected_metric: str,
        expected_trend: str,
        confidence: Literal["high", "medium", "low"],
        regression_risk: Literal["high", "medium", "low"],
        created_by: str = "governance/audit-suggestion",
    ) -> "AuditSuggestion":
        """Factory method to create suggestion with auto-generated IDs."""
        created_at = datetime.now(timezone.utc).isoformat()

        # Compute hypothesis hash for ID
        hypothesis_hash = sha256(hypothesis.encode()).hexdigest()[:8]
        suggestion_id = cls.compute_suggestion_id(created_at, hypothesis_hash)

        return cls(
            suggestion_id=suggestion_id,
            linked_observation_ids=linked_observation_ids,
            hypothesis=hypothesis,
            affected_layer=affected_layer,
            target_refs=target_refs,
            recommended_action=recommended_action,
            expected_metric=expected_metric,
            expected_trend=expected_trend,
            confidence=confidence,
            regression_risk=regression_risk,
            created_by=created_by,
            created_at=created_at,
        )
