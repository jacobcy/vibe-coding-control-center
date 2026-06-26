"""Audit decision data model for the final decision layer.

This module defines the Pydantic model for audit decisions, which structure
formal decisions on suggestions with bounded-edit contracts and gate conditions.

Decisions are published as GitHub issues (not YAML files) so the downstream
supervisor pipeline (roadmap-intake → supervisor/apply) handles execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field

_ISSUE_BODY_TEMPLATE = """## Summary

{rationale}

## Evidence Chain

**Observations**:
{observation_list}

**Suggestions**:
{suggestion_list}

## Decision

- **Type**: {decision}
- **Rationale**: {rationale}
- **Evidence strength**: {evidence_strength}
- **Requires human confirmation**: {requires_human_confirmation}

## Bounded Edit Scope

{bounded_edit_section}

## Gate Conditions (verification not yet automated)

**Note**: Gate verification is not yet automated. These conditions define the
contract for manual verification; automated checking will be added in a
future release.

{gate_conditions_section}
"""


class AuditDecision(BaseModel):
    """Structured decision record for audit feedback loop.

    Decisions are the final layer of the audit evidence model (ADR-0005):
    observation → suggestion → report → decision.

    The decision-making agent reads reports from .git/shared/reports/,
    produces formal decisions, and creates supervisor decision issues
    (not YAML files) that flow through the roadmap-intake →
    supervisor/apply pipeline. Decisions never auto-apply changes.
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
        evidence_strength: str = "medium",
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

    def format_issue_title(self) -> str:
        """Format the decision as a GitHub issue title."""
        decision_labels = {
            "accept_for_followup": "accept",
            "hold_for_more_evidence": "hold",
            "reject_with_reason": "reject",
            "split_scope": "split",
        }
        label = decision_labels.get(self.decision, self.decision)
        target = ""
        if self.bounded_edit_scope and "target_file" in self.bounded_edit_scope:
            target = f": {self.bounded_edit_scope['target_file']}"
        return f"[audit-decision] {label}{target}"

    def format_issue_body(
        self,
        evidence_strength: str = "medium",
        report_ref: str = "",
    ) -> str:
        """Format the decision as a GitHub issue body.

        Args:
            evidence_strength: Evidence strength label (strong/medium/weak/inconclusive)
            report_ref: Reference to the source report file name
        """
        observation_list = (
            "\n".join(
                f"- {oid}: [linked observation]" for oid in self.linked_observation_ids
            )
            or "- (none)"
        )

        suggestion_list = (
            "\n".join(
                f"- {sid}: [linked suggestion]" for sid in self.linked_suggestion_ids
            )
            or "- (none)"
        )

        if self.bounded_edit_scope:
            bounded_edit_section = "\n".join(
                f"- **{key}**: {value}"
                for key, value in self.bounded_edit_scope.items()
            )
            bounded_edit_section += (
                "\n\n```diff\n<!-- Provide unified diff with context -->\n```"
            )
        else:
            bounded_edit_section = "N/A (not an accept_for_followup decision)"

        if self.gate_conditions:
            gate_conditions_section = "\n".join(
                f"- **{key}**: {value}" for key, value in self.gate_conditions.items()
            )
            gate_conditions_section += (
                "\n- **Verification status**: not yet automated — manual check required"
            )
        else:
            gate_conditions_section = "N/A"

        body = _ISSUE_BODY_TEMPLATE.format(
            rationale=self.rationale,
            observation_list=observation_list,
            suggestion_list=suggestion_list,
            decision=self.decision,
            evidence_strength=evidence_strength,
            requires_human_confirmation=(
                "yes" if self.requires_human_confirmation else "no"
            ),
            bounded_edit_section=bounded_edit_section,
            gate_conditions_section=gate_conditions_section,
        )

        if report_ref:
            body += f"\n\n---\n**Source report**: {report_ref}"

        return body
