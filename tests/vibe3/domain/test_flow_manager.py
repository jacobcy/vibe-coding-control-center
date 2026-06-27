"""Test FlowManager migration to domain layer."""

from unittest.mock import MagicMock

import pytest

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo


def test_flow_manager_importable_from_domain():
    """Verify FlowManager can be imported from domain.flow_manager."""
    from vibe3.domain.flow_manager import FlowManager

    assert FlowManager is not None
    assert hasattr(FlowManager, "__init__")
    assert hasattr(FlowManager, "get_flow_for_issue")
    assert hasattr(FlowManager, "create_flow_for_issue")


def test_flow_manager_importable_from_domain_init():
    """Verify FlowManager is exported from domain.__init__."""
    from vibe3.domain import FlowManager

    assert FlowManager is not None


def test_upgrade_placeholder_creates_branch_and_worktree():
    """Test that _upgrade_placeholder bootstraps branch + worktree."""
    from vibe3.domain.flow_manager import FlowManager

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    registry = MagicMock()

    # Mock existing blocked flow with no git branch
    store.get_flow_state.return_value = {
        "branch": "task/issue-999",
        "flow_status": "blocked",
        "blocked_by_issue": 123,
    }
    git.branch_exists.return_value = False
    store.get_dependency_links.return_value = []  # No dependencies

    manager = FlowManager(
        config, store=store, git=git, github=github, registry=registry
    )

    # Mock bootstrap service
    manager._bootstrap_service.bootstrap_issue_flow = MagicMock(
        return_value={"branch": "task/issue-999", "flow_status": "active"}
    )

    issue = IssueInfo(number=999, title="Test issue")
    result = manager._upgrade_placeholder(issue, "task/issue-999")

    # Verify bootstrap was called with ensure_worktree=True
    manager._bootstrap_service.bootstrap_issue_flow.assert_called_once_with(
        issue,
        branch="task/issue-999",
        slug="issue-999",
        source="dispatch",
        ensure_worktree=True,
    )

    # Verify flow status transitioned to active
    store.update_flow_state.assert_called_once_with(
        "task/issue-999",
        flow_status="active",
        blocked_reason=None,
        blocked_by_issue=None,
        latest_actor="dispatch:upgrade_placeholder",
    )

    assert result is not None


def test_upgrade_placeholder_preserves_dependency_links():
    """Test that _upgrade_placeholder preserves dependency links."""
    from vibe3.domain.flow_manager import FlowManager

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    registry = MagicMock()

    # Mock existing blocked flow with dependencies
    store.get_flow_state.return_value = {
        "branch": "task/issue-888",
        "flow_status": "blocked",
    }
    git.branch_exists.return_value = False
    store.get_dependency_links.return_value = [123, 456]  # Two dependencies

    manager = FlowManager(
        config, store=store, git=git, github=github, registry=registry
    )

    # Mock bootstrap service
    manager._bootstrap_service.bootstrap_issue_flow = MagicMock(
        return_value={"branch": "task/issue-888", "flow_status": "active"}
    )

    # Mock task_service.link_issue for dependency re-linking
    manager.task_service.link_issue = MagicMock()

    issue = IssueInfo(number=888, title="Test issue")
    result = manager._upgrade_placeholder(issue, "task/issue-888")

    # Verify dependency links were preserved (re-linked after bootstrap)
    assert manager.task_service.link_issue.call_count == 2
    manager.task_service.link_issue.assert_any_call(
        "task/issue-888",
        issue_number=123,
        role="dependency",
        actor="dispatch:upgrade_placeholder",
    )
    manager.task_service.link_issue.assert_any_call(
        "task/issue-888",
        issue_number=456,
        role="dependency",
        actor="dispatch:upgrade_placeholder",
    )

    assert result is not None


def test_upgrade_placeholder_transitions_to_active():
    """Test that _upgrade_placeholder transitions flow_status to active."""
    from vibe3.domain.flow_manager import FlowManager

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    registry = MagicMock()

    # Mock existing blocked flow
    store.get_flow_state.return_value = {
        "branch": "task/issue-777",
        "flow_status": "blocked",
        "blocked_reason": "Waiting for dependency",
        "blocked_by_issue": 100,
    }
    git.branch_exists.return_value = False
    store.get_dependency_links.return_value = []

    manager = FlowManager(
        config, store=store, git=git, github=github, registry=registry
    )

    # Mock bootstrap service
    manager._bootstrap_service.bootstrap_issue_flow = MagicMock(
        return_value={"branch": "task/issue-777", "flow_status": "active"}
    )

    issue = IssueInfo(number=777, title="Test issue")
    result = manager._upgrade_placeholder(issue, "task/issue-777")

    # Verify update_flow_state was called with active status
    store.update_flow_state.assert_called_once()
    call_args = store.update_flow_state.call_args
    assert call_args[0][0] == "task/issue-777"
    assert call_args[1]["flow_status"] == "active"
    assert call_args[1]["blocked_reason"] is None
    assert call_args[1]["blocked_by_issue"] is None
    assert call_args[1]["latest_actor"] == "dispatch:upgrade_placeholder"

    assert result is not None


def test_is_reusable_auto_flow_rejects_terminal_statuses():
    """Terminal statuses are not reusable for dispatch (Issue #3189).

    review/failed are PR-backed terminal states and must not be treated as
    reusable active flows.
    """
    from vibe3.domain.flow_manager import FlowManager

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    git.branch_exists.return_value = True
    github = MagicMock()
    registry = MagicMock()

    manager = FlowManager(
        config, store=store, git=git, github=github, registry=registry
    )
    manager.issue_flow_service.canonical_branch_name = MagicMock(
        return_value="task/issue-3189"
    )

    for status in ("done", "aborted", "stale", "review", "failed"):
        flow = {"branch": "task/issue-3189", "flow_status": status}
        assert (
            manager._is_reusable_auto_flow(flow, 3189) is False
        ), f"{status} should not be reusable"

    for status in ("active", "blocked"):
        flow = {"branch": "task/issue-3189", "flow_status": status}
        assert (
            manager._is_reusable_auto_flow(flow, 3189) is True
        ), f"{status} should be reusable"


@pytest.mark.parametrize("flow_status", ["done", "review", "failed"])
def test_create_flow_for_issue_does_not_reactivate_pr_terminal_flow(
    flow_status: str,
) -> None:
    """The public creation entrypoint must enforce terminal-state semantics."""
    from vibe3.domain.flow_manager import FlowManager

    config = load_orchestra_config()
    store = MagicMock()
    git = MagicMock()
    git.branch_exists.return_value = True
    branch = "task/issue-3189"
    terminal_flow = {"branch": branch, "flow_status": flow_status}
    store.get_flows_by_issue.return_value = [terminal_flow]

    manager = FlowManager(
        config,
        store=store,
        git=git,
        github=MagicMock(),
        registry=MagicMock(),
    )
    manager._bootstrap_service.bootstrap_issue_flow = MagicMock()

    with pytest.raises(RuntimeError, match=f"flow is {flow_status}"):
        manager.create_flow_for_issue(IssueInfo(number=3189, title="Terminal flow"))

    manager._bootstrap_service.bootstrap_issue_flow.assert_not_called()
