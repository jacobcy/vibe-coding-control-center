"""Tests for pr_query command with --branch parameter."""

from unittest.mock import Mock, patch

import pytest

from vibe3.commands.pr_query import _resolve_pr_target
from vibe3.exceptions import UserError
from vibe3.models.pr import PRResponse, PRState


def test_resolve_pr_target_from_issue_number():
    """Test resolving PR from issue number via branch inference."""
    # Setup mocks
    pr_svc = Mock()

    # Mock flow_service with binding-based resolution
    mock_flow_service = Mock()

    # Mock store.get_flows_by_issue to return flow binding
    mock_store = Mock()
    mock_store.get_flows_by_issue.return_value = [
        {"branch": "dev/issue-946", "flow_status": "active"}
    ]
    mock_flow_service.store = mock_store

    # Mock list_prs_for_branch to return a PR
    mock_pr = PRResponse(
        number=985,
        title="feat: test",
        body="",
        state=PRState.OPEN,
        head_branch="dev/issue-946",
        base_branch="main",
        url="https://github.com/test/pr/985",
        draft=False,
        is_ready=True,
        ci_passed=False,
        ci_status=None,
    )
    pr_svc.github_client.list_prs_for_branch.return_value = [mock_pr]

    # Mock FlowService constructor
    with patch("vibe3.commands.pr_query.FlowService", return_value=mock_flow_service):
        # Call with issue number as branch parameter
        target = _resolve_pr_target(pr_svc, pr_number=None, branch="946")

    # Verify PR lookup was called with resolved branch
    assert target.pr_number == 985


def test_resolve_pr_target_branch_not_found():
    """Test fail-fast behavior when no flow found for issue number."""
    pr_svc = Mock()
    # Explicitly set empty return to avoid accidental pass
    pr_svc.github_client.list_prs_for_branch.return_value = []

    mock_flow_service = Mock()

    # Mock store.get_flows_by_issue to return empty (no binding)
    mock_store = Mock()
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None
    mock_flow_service.store = mock_store

    with patch("vibe3.commands.pr_query.FlowService", return_value=mock_flow_service):
        # Should raise UserError for missing flow (fail-fast behavior)
        with pytest.raises(UserError, match="No flow found for issue #999"):
            _resolve_pr_target(pr_svc, pr_number=None, branch="999")


def test_resolve_pr_target_no_pr_for_branch():
    """Test friendly error when branch exists but no PR found."""
    pr_svc = Mock()

    mock_flow_service = Mock()
    mock_flow_state = Mock()
    mock_flow_service.get_flow_state.return_value = mock_flow_state

    # No PRs for this branch
    pr_svc.github_client.list_prs_for_branch.return_value = []

    with patch("vibe3.commands.pr_query.FlowService", return_value=mock_flow_service):
        target = _resolve_pr_target(pr_svc, pr_number=None, branch="dev/issue-946")

    # Should return branch without PR number
    assert target.branch == "dev/issue-946"
    assert target.pr_number is None


def test_resolve_pr_target_explicit_pr_number_priority():
    """Test that explicit pr_number takes priority over branch."""
    pr_svc = Mock()

    target = _resolve_pr_target(pr_svc, pr_number=985, branch="dev/issue-946")

    # Should return both without inference
    assert target.pr_number == 985
    assert target.branch == "dev/issue-946"
    assert target.from_flow is False
