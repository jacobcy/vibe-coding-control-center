"""Tests for CheckService._check_multiple_state_labels method."""

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


def test_no_state_labels_returns_empty(check_service):
    """Test that issue with no state labels returns empty warnings/issues."""
    issue_payload = {"labels": []}

    warnings, issues, _ = check_service._check_multiple_state_labels(123, issue_payload)

    assert warnings == []
    assert issues == []


def test_single_state_label_returns_empty(check_service):
    """Test that issue with single state label returns empty warnings/issues."""
    issue_payload = {"labels": [{"name": "state/blocked"}]}

    warnings, issues, _ = check_service._check_multiple_state_labels(123, issue_payload)

    assert warnings == []
    assert issues == []


def test_multiple_state_labels_auto_fix_success(check_service):
    """Test successful auto-fix for multiple state labels."""
    issue_payload = {
        "labels": [
            {"name": "state/blocked"},
            {"name": "state/review"},
        ]
    }

    # Mock LabelService.set_state
    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues, _ = check_service._check_multiple_state_labels(
            123, issue_payload
        )

        # Should keep highest priority: blocked
        mock_label_service.set_state.assert_called_once_with(123, IssueState.BLOCKED)

        # Should return warning (auto-fix success), not issue
        assert len(warnings) == 1
        assert len(issues) == 0
        assert "auto-fixed" in warnings[0]
        assert "state/blocked" in warnings[0]
        assert "state/review" in warnings[0]


def test_multiple_state_labels_priority_order(check_service):
    """Test that highest priority state is kept (including merge-ready)."""
    test_cases = [
        # (input_labels, expected_state)
        (["state/ready", "state/blocked"], IssueState.BLOCKED),
        (["state/done", "state/in-progress"], IssueState.DONE),
        (["state/review", "state/claimed"], IssueState.REVIEW),
        (["state/merge-ready", "state/handoff"], IssueState.MERGE_READY),
        (["state/handoff", "state/claimed"], IssueState.HANDOFF),
        (["state/claimed", "state/ready"], IssueState.CLAIMED),
    ]

    for labels, expected_state in test_cases:
        issue_payload = {"labels": [{"name": label} for label in labels]}

        with patch("vibe3.services.label_service.LabelService") as mock_cls:
            mock_label_service = MagicMock()
            mock_cls.return_value = mock_label_service

            warnings, issues, _ = check_service._check_multiple_state_labels(
                123, issue_payload
            )

            mock_label_service.set_state.assert_called_once_with(123, expected_state)
            assert len(warnings) == 1
            assert len(issues) == 0


def test_unknown_state_labels_flagged_for_manual_fix(check_service):
    """Test that unknown state/* labels are flagged for manual fix."""
    issue_payload = {
        "labels": [
            {"name": "state/new-unknown-state"},
            {"name": "state/another-unknown"},
        ]
    }

    warnings, issues, _ = check_service._check_multiple_state_labels(123, issue_payload)

    # Should return issue (manual fix required), not warning
    assert len(warnings) == 0
    assert len(issues) == 1
    assert "manual fix required" in issues[0]
    assert "unknown state" in issues[0].lower()


def test_mixed_known_unknown_state_labels_keeps_known(check_service):
    """Test that known state is kept when mixed with unknown states."""
    issue_payload = {
        "labels": [
            {"name": "state/review"},
            {"name": "state/new-unknown-state"},
        ]
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues, _ = check_service._check_multiple_state_labels(
            123, issue_payload
        )

        # Should keep the known state: review
        mock_label_service.set_state.assert_called_once_with(123, IssueState.REVIEW)

        # Should return warning (auto-fix success)
        assert len(warnings) == 1
        assert len(issues) == 0


def test_auto_fix_failure_returns_manual_fix_issue(check_service):
    """Test that auto-fix failure is reported as manual fix issue."""
    issue_payload = {
        "labels": [
            {"name": "state/blocked"},
            {"name": "state/review"},
        ]
    }

    # Mock LabelService.set_state to raise exception
    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_label_service.set_state.side_effect = Exception("GitHub API error")
        mock_cls.return_value = mock_label_service

        warnings, issues, _ = check_service._check_multiple_state_labels(
            123, issue_payload
        )

        # Should return issue (manual fix required), not warning
        assert len(warnings) == 0
        assert len(issues) == 1
        assert "manual fix required" in issues[0]


def test_merge_ready_included_in_priority_list(check_service):
    """Test that merge-ready is properly handled in priority resolution."""
    issue_payload = {
        "labels": [
            {"name": "state/merge-ready"},
            {"name": "state/handoff"},
            {"name": "state/claimed"},
        ]
    }

    with patch("vibe3.services.label_service.LabelService") as mock_cls:
        mock_label_service = MagicMock()
        mock_cls.return_value = mock_label_service

        warnings, issues, _ = check_service._check_multiple_state_labels(
            123, issue_payload
        )

        # Should keep merge-ready (highest priority among the three)
        mock_label_service.set_state.assert_called_once_with(
            123, IssueState.MERGE_READY
        )

        assert len(warnings) == 1
        assert len(issues) == 0
