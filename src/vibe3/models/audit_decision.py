"""Audit decision data model for the final decision layer.

This module defines the Pydantic model for audit decisions, which represent
formal decisions on suggestions with bounded-edit contracts and gate conditions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field


class AuditDecision(BaseModel):
    """Structured decision record for audit feedback loop.

    Decisions are the final layer of the audit evidence model (ADR-0005):
    observation → suggestion → report → decision.

    The decision-making agent reads reports from .git/shared/reports/,
    produces formal decisions, and drafts follow-up issues for bounded edits.
    Decisions never auto-apply changes.
    """

    # === Identity ===
    decision_id: str = Field(description="Unique identifier: dec-<timestamp>-<hash>")
    linked_suggestion_ids: list[str] = Field(
        default_factory=list,
        description="Suggestion YAML filenames or suggestion_ids",
    )
    linked_observation_ids: list[str] = Field(
        default_factory=list,
        description="Observation YAML filenames or observation_ids",
    )

    # === Decision ===
    decision: Literal[
        "accept_for_followup",
        "hold_for_more_evidence",
        "reject_with_reason",
        "split_scope",
    ] = Field(description="Decision type")

    rationale: str = Field(description="Why this decision was made")

    # === Bounded Edit Contract (only for accept_for_followup) ===
    bounded_edit_scope: dict[str, str | int] | None = Field(
        default=None,
        description="Bounded edit scope: target_file, target_section, max_lines",
    )

    # === Gate/Rollback Contract ===
    gate_conditions: dict[str, str | int] | None = Field(
        default=None,
        description=(
            "Gate conditions: verification_window_days, "
            "rollback_trigger, success_metric"
        ),
    )

    # === Human Confirmation ===
    requires_human_confirmation: bool = Field(
        default=True,
        description="True for high-impact changes requiring human approval",
    )

    # === Metadata ===
    created_by: str = Field(
        default="governance/audit-decision", description="Creator identifier"
    )
    created_at: str = Field(description="ISO 8601 timestamp")

    # === Hard Default: No Auto-Apply ===
    auto_apply: bool = Field(
        default=False,
        description="Hard default: decisions never auto-apply changes",
    )

    @staticmethod
    def compute_decision_id(timestamp: str, rationale_hash: str) -> str:
        """Generate unique decision ID."""
        clean_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
        hash_suffix = sha256(f"{timestamp}-{rationale_hash}".encode()).hexdigest()[:8]
        return f"dec-{clean_ts}-{hash_suffix}"

    @classmethod
    def create(
        cls,
        decision: Literal[
            "accept_for_followup",
            "hold_for_more_evidence",
            "reject_with_reason",
            "split_scope",
        ],
        rationale: str,
        linked_suggestion_ids: list[str],
        linked_observation_ids: list[str],
        bounded_edit_scope: dict[str, str | int] | None = None,
        gate_conditions: dict[str, str | int] | None = None,
        requires_human_confirmation: bool = True,
        created_by: str = "governance/audit-decision",
    ) -> "AuditDecision":
        """Factory method to create decision with auto-generated ID."""
        created_at = datetime.now(timezone.utc).isoformat()

        # Compute rationale hash for ID
        rationale_hash = sha256(rationale.encode()).hexdigest()[:8]
        decision_id = cls.compute_decision_id(created_at, rationale_hash)

        return cls(
            decision_id=decision_id,
            decision=decision,
            rationale=rationale,
            linked_suggestion_ids=linked_suggestion_ids,
            linked_observation_ids=linked_observation_ids,
            bounded_edit_scope=bounded_edit_scope,
            gate_conditions=gate_conditions,
            requires_human_confirmation=requires_human_confirmation,
            created_by=created_by,
            created_at=created_at,
        )
