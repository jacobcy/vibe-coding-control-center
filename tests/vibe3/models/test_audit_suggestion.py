"""Tests for AuditSuggestion model."""

import pytest
from pydantic import ValidationError

from vibe3.models.audit_suggestion import AuditSuggestion


def test_create_suggestion():
    """Test factory method produces valid model."""
    suggestion = AuditSuggestion.create(
        hypothesis="Test hypothesis",
        linked_observation_ids=["obs-001", "obs-002"],
        affected_layer="prompt_material",
        target_refs=["supervisor/governance/example.md"],
        recommended_action="bounded_edit",
        expected_metric="Error rate in phase execution",
        expected_trend="decrease",
        confidence="medium",
        regression_risk="low",
    )
    assert suggestion.suggestion_id.startswith("sug-")
    assert suggestion.hypothesis == "Test hypothesis"
    assert len(suggestion.linked_observation_ids) == 2
    assert suggestion.affected_layer == "prompt_material"
    assert suggestion.created_by == "governance/audit-suggestion"


def test_suggestion_id_format():
    """Test ID matches sug-... pattern."""
    suggestion = AuditSuggestion.create(
        hypothesis="Test",
        linked_observation_ids=["obs-001"],
        affected_layer="runtime",
        target_refs=[],
        recommended_action="no_action",
        expected_metric="Test metric",
        expected_trend="stabilize",
        confidence="low",
        regression_risk="low",
    )
    assert suggestion.suggestion_id.startswith("sug-")
    parts = suggestion.suggestion_id.split("-")
    assert len(parts) >= 3  # sug, timestamp, hash


def test_required_fields():
    """Test missing fields raise ValidationError."""
    with pytest.raises(ValidationError):
        AuditSuggestion()  # Missing all required fields


def test_affected_layer_values():
    """Test invalid layer raises ValidationError."""
    with pytest.raises(ValidationError):
        AuditSuggestion.create(
            hypothesis="Test",
            linked_observation_ids=[],
            affected_layer="invalid_layer",  # type: ignore
            target_refs=[],
            recommended_action="no_action",
            expected_metric="Test",
            expected_trend="stable",
            confidence="medium",
            regression_risk="low",
        )


def test_recommended_action_values():
    """Test invalid action raises ValidationError."""
    with pytest.raises(ValidationError):
        AuditSuggestion.create(
            hypothesis="Test",
            linked_observation_ids=[],
            affected_layer="runtime",
            target_refs=[],
            recommended_action="invalid_action",  # type: ignore
            expected_metric="Test",
            expected_trend="stable",
            confidence="medium",
            regression_risk="low",
        )


def test_confidence_values():
    """Test invalid confidence raises ValidationError."""
    with pytest.raises(ValidationError):
        AuditSuggestion.create(
            hypothesis="Test",
            linked_observation_ids=[],
            affected_layer="runtime",
            target_refs=[],
            recommended_action="no_action",
            expected_metric="Test",
            expected_trend="stable",
            confidence="invalid",  # type: ignore
            regression_risk="low",
        )


def test_regression_risk_values():
    """Test invalid risk raises ValidationError."""
    with pytest.raises(ValidationError):
        AuditSuggestion.create(
            hypothesis="Test",
            linked_observation_ids=[],
            affected_layer="runtime",
            target_refs=[],
            recommended_action="no_action",
            expected_metric="Test",
            expected_trend="stable",
            confidence="medium",
            regression_risk="invalid",  # type: ignore
        )


def test_json_roundtrip():
    """Test model can serialize/deserialize."""
    suggestion = AuditSuggestion.create(
        hypothesis="Test hypothesis",
        linked_observation_ids=["obs-001"],
        affected_layer="prompt_material",
        target_refs=["test.md"],
        recommended_action="create_followup",
        expected_metric="Test metric",
        expected_trend="increase",
        confidence="high",
        regression_risk="medium",
    )
    # Serialize to dict
    data = suggestion.model_dump()
    # Deserialize back
    restored = AuditSuggestion.model_validate(data)
    assert restored.suggestion_id == suggestion.suggestion_id
    assert restored.hypothesis == suggestion.hypothesis
    assert restored.affected_layer == suggestion.affected_layer


def test_compute_suggestion_id():
    """Test static ID computation."""
    suggestion_id = AuditSuggestion.compute_suggestion_id(
        "2026-06-23T12:00:00.000000", "abc12345"
    )
    assert suggestion_id.startswith("sug-")
    assert "20260623T120000" in suggestion_id.replace(":", "").replace("-", "")


def test_all_affected_layers():
    """Test all valid affected layer values."""
    valid_layers = [
        "runtime",
        "prompt_recipe",
        "prompt_material",
        "skill_contract",
        "governance_policy",
        "repo_profile",
        "memory_signal",
    ]
    for layer in valid_layers:
        suggestion = AuditSuggestion.create(
            hypothesis=f"Test for {layer}",
            linked_observation_ids=[],
            affected_layer=layer,  # type: ignore
            target_refs=[],
            recommended_action="no_action",
            expected_metric="Test",
            expected_trend="stable",
            confidence="low",
            regression_risk="low",
        )
        assert suggestion.affected_layer == layer


def test_all_recommended_actions():
    """Test all valid action values."""
    valid_actions = [
        "no_action",
        "create_followup",
        "bounded_edit",
        "evaluate_more",
    ]
    for action in valid_actions:
        suggestion = AuditSuggestion.create(
            hypothesis=f"Test for {action}",
            linked_observation_ids=[],
            affected_layer="runtime",
            target_refs=[],
            recommended_action=action,  # type: ignore
            expected_metric="Test",
            expected_trend="stable",
            confidence="low",
            regression_risk="low",
        )
        assert suggestion.recommended_action == action
