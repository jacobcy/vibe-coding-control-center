"""Tests for coordination truth table model."""

import pytest
from pydantic import ValidationError

from vibe3.models.coordination_truth import CoordinationTruth
from vibe3.models.data_source import DataSource


def test_default_truth():
    """Test default truth is not blocked."""
    truth = CoordinationTruth()
    assert truth.is_blocked is False
    assert truth.blocked_reason is None
    assert truth.blocked_by_issue is None
    assert truth.dependencies == []


def test_blocked_truth_from_reason():
    """Test blocked state inferred from blocked_reason."""
    truth = CoordinationTruth(
        blocked_reason="API design pending",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is True
    assert truth.blocked_reason == "API design pending"


def test_blocked_truth_from_issue():
    """Test blocked state inferred from blocked_by_issues."""
    truth = CoordinationTruth(
        blocked_by_issues=[456],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is True
    assert truth.blocked_by_issue == 456  # computed property for backward compat


def test_truth_with_dependencies():
    """Test truth tracks dependencies."""
    truth = CoordinationTruth(
        dependencies=[123, 789],
        dependencies_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.dependencies == [123, 789]
    assert truth.is_blocked is False  # Dependencies alone don't block


def test_truth_provenance():
    """Test truth tracks data source provenance."""
    truth = CoordinationTruth(
        blocked_reason="Local block",
        blocked_reason_source=DataSource.LOCAL_SQLITE,
        worktree_path="/tmp/worktree",
    )
    assert truth.blocked_reason_source == DataSource.LOCAL_SQLITE
    assert truth.worktree_path == "/tmp/worktree"


def test_source_required_for_blocked_reason():
    """Test that blocked_reason requires blocked_reason_source."""
    with pytest.raises(ValidationError, match="blocked_reason_source must be set"):
        CoordinationTruth(blocked_reason="Missing source")


def test_source_required_for_blocked_by_issue():
    """Test that blocked_by_issues requires blocked_by_issue_source."""
    with pytest.raises(ValidationError, match="blocked_by_issue_source must be set"):
        CoordinationTruth(blocked_by_issues=[999])


def test_source_required_for_dependencies():
    """Test that dependencies require dependencies_source."""
    with pytest.raises(ValidationError, match="dependencies_source must be set"):
        CoordinationTruth(dependencies=[123])


def test_empty_dependencies_no_source():
    """Test that empty dependencies list doesn't require source."""
    truth = CoordinationTruth(dependencies=[])
    assert truth.dependencies == []
    assert truth.dependencies_source is None


def test_is_blocked_in_serialization():
    """Test that is_blocked appears in model_dump() output."""
    truth = CoordinationTruth(
        blocked_reason="Blocked",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    dumped = truth.model_dump()
    assert "is_blocked" in dumped
    assert dumped["is_blocked"] is True


def test_blocked_from_projection_state():
    """Test blocked state inferred from projection_state='blocked'."""
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is True
    assert truth.projection_state == "blocked"


def test_blocked_from_projection_state_without_reason():
    """Body State: blocked without reason => still treated as blocked.

    Projection inconsistency requiring alignment, but blocked truth wins.
    """
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    # Even without blocked_reason or blocked_by_issue, state=blocked means blocked
    assert truth.is_blocked is True


def test_blocked_from_projection_state_and_payload():
    """Body State: blocked + reason => blocked truth."""
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_reason="API design pending",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is True
    assert truth.blocked_reason == "API design pending"


def test_not_blocked_with_active_projection():
    """Body State: active with no blocked payload => not blocked."""
    truth = CoordinationTruth(
        projection_state="active",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is False


def test_local_fallback_blocks_on_cache():
    """Remote read failure => local fallback with blocked cache.

    When remote fails and local has blocked_reason, projection_state
    is inferred as 'blocked' from the local cache.
    """
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.LOCAL_SQLITE,
        blocked_reason="Health check failed",
        blocked_reason_source=DataSource.LOCAL_SQLITE,
    )
    assert truth.is_blocked is True
    assert truth.projection_state_source == DataSource.LOCAL_SQLITE


def test_source_required_for_projection_state():
    """Test that projection_state requires projection_state_source."""
    with pytest.raises(ValidationError, match="projection_state_source must be set"):
        CoordinationTruth(projection_state="blocked")
