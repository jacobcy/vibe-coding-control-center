"""Unit tests for AuditDecision model."""

from datetime import datetime, timezone

import pytest

from vibe3.models.audit_decision import AuditDecision


def test_audit_decision_create_factory():
    """Test AuditDecision.create() factory method."""
    decision = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Strong evidence from 3 observations",
        linked_suggestion_ids=["sug-001", "sug-002"],
        linked_observation_ids=["obs-001", "obs-002", "obs-003"],
        bounded_edit_scope={
            "target_file": "supervisor/governance/example.md",
            "target_section": "## Execution Pattern",
            "max_lines": 50,
        },
        gate_conditions={
            "verification_window_days": 7,
            "rollback_trigger": "blocked rate > 10%",
            "success_metric": "flow blocked rate",
        },
        requires_human_confirmation=False,
    )

    assert decision.decision_id.startswith("dec-")
    assert decision.decision == "accept_for_followup"
    assert decision.rationale == "Strong evidence from 3 observations"
    assert len(decision.linked_suggestion_ids) == 2
    assert len(decision.linked_observation_ids) == 3
    assert decision.bounded_edit_scope is not None
    assert decision.gate_conditions is not None
    assert decision.requires_human_confirmation is False
    assert decision.auto_apply is False  # Hard default


def test_audit_decision_id_uniqueness():
    """Test that decision_id generation is unique."""
    decision1 = AuditDecision.create(
        decision="hold_for_more_evidence",
        rationale="Weak evidence, need more observations",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
    )

    # Wait a tiny bit to ensure different timestamp (though hash should differ anyway)
    decision2 = AuditDecision.create(
        decision="hold_for_more_evidence",
        rationale="Weak evidence, need more observations",  # Same rationale
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
    )

    # IDs should be different (timestamp-based)
    assert decision1.decision_id != decision2.decision_id


def test_audit_decision_serialization():
    """Test AuditDecision serialization to dict."""
    decision = AuditDecision.create(
        decision="reject_with_reason",
        rationale="Inconclusive evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
    )

    data = decision.model_dump()

    assert "decision_id" in data
    assert data["decision"] == "reject_with_reason"
    assert data["rationale"] == "Inconclusive evidence"
    assert data["auto_apply"] is False


def test_audit_decision_deserialization():
    """Test AuditDecision deserialization from dict."""
    created_at = datetime.now(timezone.utc).isoformat()

    data = {
        "decision_id": "dec-20260623T123456-abc123de",
        "decision": "split_scope",
        "rationale": "Multiple unrelated issues",
        "linked_suggestion_ids": ["sug-001", "sug-002"],
        "linked_observation_ids": ["obs-001", "obs-002"],
        "created_by": "governance/audit-decision",
        "created_at": created_at,
        "auto_apply": False,
    }

    decision = AuditDecision(**data)

    assert decision.decision_id == "dec-20260623T123456-abc123de"
    assert decision.decision == "split_scope"
    assert decision.rationale == "Multiple unrelated issues"


def test_audit_decision_bounded_edit_scope_validation():
    """Test bounded_edit_scope field validation."""
    # Valid bounded_edit_scope
    decision1 = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Strong evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001", "obs-002"],
        bounded_edit_scope={
            "target_file": "test.md",
            "target_section": "## Test",
            "max_lines": 100,
        },
    )
    assert decision1.bounded_edit_scope is not None
    assert decision1.bounded_edit_scope["target_file"] == "test.md"

    # Missing bounded_edit_scope (should be None)
    decision2 = AuditDecision.create(
        decision="hold_for_more_evidence",
        rationale="Weak evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
        bounded_edit_scope=None,
    )
    assert decision2.bounded_edit_scope is None


def test_audit_decision_gate_conditions_validation():
    """Test gate_conditions field validation."""
    # Valid gate_conditions
    decision1 = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Strong evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001", "obs-002"],
        gate_conditions={
            "verification_window_days": 7,
            "rollback_trigger": "blocked rate > 10%",
            "success_metric": "flow blocked rate",
        },
    )
    assert decision1.gate_conditions is not None
    assert decision1.gate_conditions["verification_window_days"] == 7

    # Missing gate_conditions (should be None)
    decision2 = AuditDecision.create(
        decision="reject_with_reason",
        rationale="Inconclusive evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
        gate_conditions=None,
    )
    assert decision2.gate_conditions is None


def test_audit_decision_auto_apply_hard_default():
    """Test that auto_apply has hard default False."""
    # Explicitly set to False
    decision1 = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Test",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
        requires_human_confirmation=False,
    )
    assert decision1.auto_apply is False

    # Create without specifying (should default to False)
    decision2 = AuditDecision(
        decision_id="dec-test",
        decision="accept_for_followup",
        rationale="Test",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
        created_by="test",
        created_at=datetime.now(timezone.utc).isoformat(),
        # Note: auto_apply not specified
    )
    assert decision2.auto_apply is False


def test_audit_decision_decision_type_validation():
    """Test decision field Literal type validation."""
    # Valid decision types
    valid_decisions = [
        "accept_for_followup",
        "hold_for_more_evidence",
        "reject_with_reason",
        "split_scope",
    ]

    for decision_type in valid_decisions:
        decision = AuditDecision.create(
            decision=decision_type,
            rationale=f"Test {decision_type}",
            linked_suggestion_ids=["sug-001"],
            linked_observation_ids=["obs-001"],
        )
        assert decision.decision == decision_type

    # Invalid decision type should raise validation error
    with pytest.raises(Exception):  # Pydantic validation error
        AuditDecision.create(
            decision="invalid_type",  # Not in Literal
            rationale="Test invalid",
            linked_suggestion_ids=["sug-001"],
            linked_observation_ids=["obs-001"],
        )


def test_format_issue_title():
    """Test that format_issue_title produces valid GitHub issue title."""
    decision = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Strong evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001", "obs-002"],
        bounded_edit_scope={
            "target_file": "supervisor/governance/example.md",
            "max_lines": 50,
        },
        evidence_strength="strong",
    )
    title = decision.format_issue_title()
    assert title.startswith("[audit-decision]")
    assert "accept" in title
    assert "supervisor/governance/example.md" in title


def test_format_issue_title_no_target():
    """format_issue_title without bounded_edit_scope."""
    decision = AuditDecision.create(
        decision="hold_for_more_evidence",
        rationale="Weak evidence",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
    )
    title = decision.format_issue_title()
    assert title.startswith("[audit-decision]")
    assert "hold" in title


def test_format_issue_body_accept():
    """format_issue_body produces complete issue body for accept decision."""
    decision = AuditDecision.create(
        decision="accept_for_followup",
        rationale="Strong evidence from 3 observations, clear target refs",
        linked_suggestion_ids=["sug-001", "sug-002"],
        linked_observation_ids=["obs-001", "obs-002", "obs-003"],
        bounded_edit_scope={
            "target_file": "supervisor/governance/example.md",
            "target_section": "## Execution Pattern",
            "max_lines": 50,
        },
        gate_conditions={
            "verification_window_days": 7,
            "rollback_trigger": "blocked rate > 10%",
            "success_metric": "flow blocked rate",
        },
        evidence_strength="strong",
    )
    body = decision.format_issue_body(
        evidence_strength="strong",
        report_ref="audit-report-20260623T120000.md",
    )

    # Verify key sections are present
    assert "## Summary" in body
    assert "Strong evidence" in body
    assert "## Evidence Chain" in body
    assert "obs-001" in body
    assert "sug-001" in body
    assert "## Decision" in body
    assert "accept_for_followup" in body
    assert "## Bounded Edit Scope" in body
    assert "target_file" in body
    assert "## Gate Conditions" in body
    assert "verification_window_days" in body
    assert "not yet automated" in body
    assert "audit-report-20260623T120000.md" in body


def test_format_issue_body_no_gate_conditions():
    """format_issue_body handles missing gate_conditions."""
    decision = AuditDecision.create(
        decision="hold_for_more_evidence",
        rationale="Weak evidence, need more observations",
        linked_suggestion_ids=["sug-001"],
        linked_observation_ids=["obs-001"],
    )
    body = decision.format_issue_body(evidence_strength="weak")
    assert "## Gate Conditions" in body
    assert "N/A" in body


def test_format_issue_body_empty_linked_ids():
    """format_issue_body handles empty linked IDs gracefully."""
    decision = AuditDecision.create(
        decision="reject_with_reason",
        rationale="Inconclusive evidence, contradictory observations",
        linked_suggestion_ids=[],
        linked_observation_ids=[],
    )
    body = decision.format_issue_body(evidence_strength="inconclusive")
    assert "(none)" in body
