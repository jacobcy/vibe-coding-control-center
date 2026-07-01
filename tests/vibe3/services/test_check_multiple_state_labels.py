"""Tests for CheckService._check_multiple_state_labels method."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.check.service import CheckService


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
    with patch("vibe3.services.shared.label_service.LabelService") as mock_cls:
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

        with patch("vibe3.services.shared.label_service.LabelService") as mock_cls:
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

    with patch("vibe3.services.shared.label_service.LabelService") as mock_cls:
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
    with patch("vibe3.services.shared.label_service.LabelService") as mock_cls:
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

    with patch("vibe3.services.shared.label_service.LabelService") as mock_cls:
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


class TestIssueStateFromPayload:
    """Direct unit tests for issue_state_from_payload() function."""

    def test_github_order_differs_from_priority(self):
        """Test that priority order wins, not GitHub API order."""
        from vibe3.services.check.remote import issue_state_from_payload

        # GitHub returns [blocked, ready], but blocked has higher priority
        issue = {"labels": [{"name": "state/blocked"}, {"name": "state/ready"}]}
        result = issue_state_from_payload(issue)
        assert result == IssueState.BLOCKED

    def test_github_order_reversed_vs_priority(self):
        """Test that priority wins when GitHub lists in reverse."""
        from vibe3.services.check.remote import issue_state_from_payload

        # GitHub returns [ready, handoff, blocked], but blocked is highest
        issue = {
            "labels": [
                {"name": "state/ready"},
                {"name": "state/handoff"},
                {"name": "state/blocked"},
            ]
        }
        result = issue_state_from_payload(issue)
        assert result == IssueState.BLOCKED

    def test_single_state_label(self):
        """Test that single state label is correctly extracted."""
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": [{"name": "state/handoff"}]}
        result = issue_state_from_payload(issue)
        assert result == IssueState.HANDOFF

    def test_no_state_labels(self):
        """Test that non-state labels return None."""
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": [{"name": "priority/high"}, {"name": "bug"}]}
        result = issue_state_from_payload(issue)
        assert result is None

    def test_non_list_labels(self):
        """Test that non-list labels field returns None."""
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": "not-a-list"}
        result = issue_state_from_payload(issue)
        assert result is None

    def test_not_a_dict(self):
        """Test that non-dict payload returns None."""
        from vibe3.services.check.remote import issue_state_from_payload

        result = issue_state_from_payload("not-a-dict")
        assert result is None

    def test_mixed_known_unknown_state(self):
        """Test that unknown state prefixes are ignored, known wins."""
        from vibe3.services.check.remote import issue_state_from_payload

        # state/unknown-future is not in priority order, state/review is
        issue = {
            "labels": [
                {"name": "state/unknown-future"},
                {"name": "state/review"},
            ]
        }
        result = issue_state_from_payload(issue)
        assert result == IssueState.REVIEW

    def test_empty_labels(self):
        """Test that empty labels list returns None."""
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": []}
        result = issue_state_from_payload(issue)
        assert result is None


class TestIssueStateFromFlowState:
    """Direct unit tests for issue_state_from_payload() flow-truth path.

    When a ``FlowState`` is supplied, the local execution artifacts
    (``pr_ref`` / ``report_ref`` / ``latest_verdict`` etc.) take precedence
    over whatever GitHub API happened to return — matching the semantics of
    ``vibe3 task resume --label auto``.
    """

    def test_flow_with_report_ref_overrides_stale_labels(self):
        """plan_ref + report_ref -> REVIEW, even if issue still has stale labels."""
        from vibe3.models import FlowState
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {
            "labels": [
                {"name": "state/blocked"},
                {"name": "state/ready"},
            ]
        }
        flow_state = FlowState(
            branch="task/issue-1",
            flow_slug="default",
            flow_status="active",
            plan_ref="runs/1",
            report_ref="runs/123",
        )
        result = issue_state_from_payload(issue, flow_state=flow_state)
        assert result == IssueState.REVIEW

    def test_flow_with_pr_ref_overrides_priority(self):
        """Flow with pr_ref -> HANDOFF, even if issue has higher-priority labels."""
        from vibe3.models import FlowState
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {
            "labels": [
                {"name": "state/blocked"},
                {"name": "state/review"},
            ]
        }
        flow_state = FlowState(
            branch="task/issue-1",
            flow_slug="default",
            flow_status="active",
            pr_ref="https://github.com/x/pull/1",
        )
        result = issue_state_from_payload(issue, flow_state=flow_state)
        assert result == IssueState.HANDOFF

    def test_flow_with_plan_ref_only(self):
        """Flow with only plan_ref -> IN_PROGRESS."""
        from vibe3.models import FlowState
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": [{"name": "state/ready"}]}
        flow_state = FlowState(
            branch="task/issue-1",
            flow_slug="default",
            flow_status="active",
            plan_ref="runs/1",
        )
        result = issue_state_from_payload(issue, flow_state=flow_state)
        assert result == IssueState.IN_PROGRESS

    def test_flow_with_pass_verdict(self):
        """Flow with PASS verdict -> MERGE_READY."""
        from vibe3.models import FlowState, VerdictRecord
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {"labels": [{"name": "state/review"}]}
        flow_state = FlowState(
            branch="task/issue-1",
            flow_slug="default",
            flow_status="active",
            latest_verdict=VerdictRecord(
                verdict="PASS",
                actor="test",
                role="reviewer",
                timestamp="2026-01-01T00:00:00",
                flow_branch="task/issue-1",
            ),
        )
        result = issue_state_from_payload(issue, flow_state=flow_state)
        assert result == IssueState.MERGE_READY

    def test_flow_state_as_partial_dict_degraded_to_fallback(self):
        """Dict rows missing required fields must degrade to static fallback.

        This mirrors the service-layer tolerant path: partial dict rows from
        test mocks (or schema-drift SQLite snapshots) drop to
        ``get_highest_priority_state`` instead of crashing.
        """
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {
            "labels": [
                {"name": "state/ready"},
                {"name": "state/blocked"},
            ]
        }
        # Missing required `branch` and `flow_slug` fields.
        result = issue_state_from_payload(issue, flow_state={})
        assert result == IssueState.BLOCKED

    def test_flow_state_as_partial_dict_missing_verdict(self):
        """Dict row without verdict/refs falls back to READY (no plan_ref).

        When the local flow has no pr_ref / verdict / report_ref / plan_ref,
        ``infer_resume_label`` returns READY — the canonical "ready to be
        picked up" state.  This is the flow-truth authority, so it wins over
        the stale GitHub labels.
        """
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {
            "labels": [
                {"name": "state/review"},
                {"name": "state/handoff"},
            ]
        }
        flow_state = {
            "branch": "task/issue-1",
            "flow_slug": "default",
            "flow_status": "active",
        }
        result = issue_state_from_payload(issue, flow_state=flow_state)
        assert result == IssueState.READY

    def test_no_flow_state_falls_back_to_priority(self):
        """Without flow_state, fall back to static priority order."""
        from vibe3.services.check.remote import issue_state_from_payload

        issue = {
            "labels": [
                {"name": "state/ready"},
                {"name": "state/blocked"},
            ]
        }
        result = issue_state_from_payload(issue)
        assert result == IssueState.BLOCKED
