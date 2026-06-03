"""End-to-end integration tests for health check flow."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check_service import CheckService


def test_closed_issue_flow_check_returns_invalid_e2e(temp_store: SQLiteClient) -> None:
    """CheckService reports closed issue as invalid but does not abort the flow.

    Flow termination (marking as aborted) is QualifyGate's responsibility.
    CheckService is a pure structural validator that only reports invalidity.
    """
    branch = "task/issue-789"

    # Setup: create flow in active state with task issue link
    temp_store.update_flow_state(branch, flow_slug="test_flow", flow_status="active")
    temp_store.add_issue_link(branch, 789, "task")

    # Verify initial state
    flow_data = temp_store.get_flow_state(branch)
    assert flow_data is not None
    assert flow_data["flow_status"] == "active"

    # Simulate: user closes issue on GitHub
    # Run: CheckService discovers closed issue
    mock_git = MagicMock(spec=GitClient)
    mock_git.find_worktree_path_for_branch.return_value = None

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.view_issue.return_value = {
        "number": 789,
        "state": "CLOSED",
        "labels": [],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []  # No PRs for branch
    mock_github.close_issue_if_open.return_value = (
        "already_closed"  # Issue already closed
    )

    service = CheckService(
        store=temp_store,
        git_client=mock_git,
        github_client=mock_github,
    )
    service._initialize_pr_cache()

    result = service.verify_branch(branch)

    # Verify: check result reports invalid (closed issue = not valid for dispatch)
    assert result.is_valid is False
    assert any("CLOSED" in issue for issue in result.issues)
    assert result.branch == branch

    # Verify: flow remains active — CheckService no longer aborts flows.
    # QualifyGate.run_qualify_gate() handles flow termination via cleanup_flow_scene().
    flow_data = temp_store.get_flow_state(branch)
    assert flow_data is not None
    assert flow_data["flow_status"] == "active"
