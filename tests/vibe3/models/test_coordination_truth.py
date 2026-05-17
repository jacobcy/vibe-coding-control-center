"""Tests for coordination truth table model."""

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
    """Test blocked state inferred from blocked_by_issue."""
    truth = CoordinationTruth(
        blocked_by_issue=456,
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )
    assert truth.is_blocked is True
    assert truth.blocked_by_issue == 456


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
