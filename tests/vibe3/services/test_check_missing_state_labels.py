"""Tests for CheckService._check_missing_state_labels method."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.check_service import CheckService


@pytest.fixture
def mock_store():
    """Create a mock SQLite store."""
    return MagicMock()


@pytest.fixture
def mock_git_client():
    """Create a mock Git client."""
    return MagicMock()


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client."""
    return MagicMock()


@pytest.fixture
def check_service(mock_store, mock_git_client, mock_github_client):
    """Create a CheckService instance with mocked dependencies."""
    return CheckService(
        store=mock_store,
        git_client=mock_git_client,
        github_client=mock_github_client,
    )


def test_missing_state_labels_restores_from_plan_ref(check_service):
    """Test that missing state labels are restored when flow has plan_ref."""
    flow_data = {
        "branch": "task/issue-123",
        "flow_slug": "issue-123",
        "plan_ref": "docs/plans/issue-123.md",
        # No report_ref, pr_ref, or verdict -> should be IN_PROGRESS
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(123, flow_data)

        # Should restore to IN_PROGRESS (has plan_ref but no report_ref)
        mock_label_service.set_state.assert_called_once_with(
            123, IssueState.IN_PROGRESS
        )

        # Should return warning (auto-restore success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-restored" in warnings[0]
        assert "state/in-progress" in warnings[0]


def test_missing_state_labels_restores_from_report_ref(check_service):
    """Test that missing state labels are restored when flow has report_ref."""
    flow_data = {
        "branch": "task/issue-456",
        "flow_slug": "issue-456",
        "plan_ref": "docs/plans/issue-456.md",
        "report_ref": "docs/reports/issue-456.md",
        # Has plan and report -> should be REVIEW
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(456, flow_data)

        # Should restore to REVIEW (has plan_ref and report_ref)
        mock_label_service.set_state.assert_called_once_with(456, IssueState.REVIEW)

        # Should return warning (auto-restore success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-restored" in warnings[0]
        assert "state/review" in warnings[0]


def test_missing_state_labels_restores_from_pr_ref(check_service):
    """Test that missing state labels are restored when flow has pr_ref."""
    flow_data = {
        "branch": "task/issue-789",
        "flow_slug": "issue-789",
        "plan_ref": "docs/plans/issue-789.md",
        "report_ref": "docs/reports/issue-789.md",
        "pr_ref": "refs/pull/123",
        # Has PR -> should be HANDOFF
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(789, flow_data)

        # Should restore to HANDOFF (has pr_ref)
        mock_label_service.set_state.assert_called_once_with(789, IssueState.HANDOFF)

        # Should return warning (auto-restore success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-restored" in warnings[0]
        assert "state/handoff" in warnings[0]


def test_missing_state_labels_restores_to_claimed_when_no_artifacts(check_service):
    """Test that missing state labels are restored to CLAIMED when no artifacts."""
    flow_data = {
        "branch": "task/issue-999",
        "flow_slug": "issue-999",
        # No plan_ref, report_ref, pr_ref, or verdict -> should be CLAIMED
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(999, flow_data)

        # Should restore to CLAIMED (no artifacts)
        mock_label_service.set_state.assert_called_once_with(999, IssueState.CLAIMED)

        # Should return warning (auto-restore success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-restored" in warnings[0]
        assert "state/claimed" in warnings[0]


def test_missing_state_labels_restore_failure_returns_manual_fix_issue(check_service):
    """Test that restore failure is reported as manual fix issue."""
    flow_data = {
        "branch": "task/issue-123",
        "flow_slug": "issue-123",
        "plan_ref": "docs/plans/issue-123.md",
    }

    # Mock LabelService.set_state to raise exception
    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_label_service.set_state.side_effect = Exception("GitHub API error")
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(123, flow_data)

        # Should return issue (manual fix required), not warning
        assert len(warnings) == 0
        assert len(issues) == 1
        assert "manual fix required" in issues[0]
        assert "no state label" in issues[0]


def test_missing_state_labels_handles_flow_state_validation_error(check_service):
    """Test that invalid flow_data is handled gracefully."""
    flow_data = {
        "branch": "task/issue-123",
        # Missing required field 'flow_slug' -> validation error
    }

    warnings, issues = check_service._check_missing_state_labels(123, flow_data)

    # Should return issue (manual fix required), not warning
    assert len(warnings) == 0
    assert len(issues) == 1
    assert "manual fix required" in issues[0]


def test_missing_state_labels_restores_from_pass_verdict(check_service):
    """Test that missing state labels are restored when flow has PASS verdict."""

    flow_data = {
        "branch": "task/issue-111",
        "flow_slug": "issue-111",
        "plan_ref": "docs/plans/issue-111.md",
        "report_ref": "docs/reports/issue-111.md",
        "latest_verdict": {
            "verdict": "PASS",
            "actor": "claude/opus",
            "role": "reviewer",
            "timestamp": "2026-06-03T00:00:00Z",
            "flow_branch": "task/issue-111",
        },
        # PASS verdict -> should be MERGE_READY
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(111, flow_data)

        # Should restore to MERGE_READY (PASS verdict)
        mock_label_service.set_state.assert_called_once_with(
            111, IssueState.MERGE_READY
        )

        # Should return warning (auto-restore success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-restored" in warnings[0]
        assert "state/merge-ready" in warnings[0]


def test_missing_state_labels_restores_from_minor_verdict_with_audit(check_service):
    """Test MINOR verdict with audit_ref restores to MERGE_READY."""

    flow_data = {
        "branch": "task/issue-222",
        "flow_slug": "issue-222",
        "plan_ref": "docs/plans/issue-222.md",
        "report_ref": "docs/reports/issue-222.md",
        "latest_verdict": {
            "verdict": "MINOR",
            "actor": "claude/opus",
            "role": "reviewer",
            "timestamp": "2026-06-03T00:00:00Z",
            "flow_branch": "task/issue-222",
        },
        "audit_ref": "docs/audits/issue-222.md",
        # MINOR verdict with audit_ref -> should be MERGE_READY
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues = check_service._check_missing_state_labels(222, flow_data)

        # Should restore to MERGE_READY (MINOR verdict with audit_ref)
        mock_label_service.set_state.assert_called_once_with(
            222, IssueState.MERGE_READY
        )

        assert len(warnings) == 1
        assert len(issues) == 0
