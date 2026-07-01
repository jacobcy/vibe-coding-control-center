"""Tests for DependencyRecheckService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models import IssueResolvedDependency, IssueState
from vibe3.services.dispatch.dependency_recheck_service import (
    DependencyRecheckService,
)


def test_handle_issue_resolved_no_dependents(temp_store: SQLiteClient) -> None:
    """Test that service returns empty result when no dependents found."""
    github_client = MagicMock()
    service = DependencyRecheckService(store=temp_store, github_client=github_client)

    event = IssueResolvedDependency(issue_number=999, merged=True)

    result = service.handle_issue_resolved(event)

    assert result.issue_number == 999
    assert result.dependents_checked == 0
    assert result.unblocked == 0
    assert result.still_blocked == 0
    assert result.errors == 0


def test_handle_issue_resolved_with_dependents(temp_store: SQLiteClient) -> None:
    """Test that service calls reconcile_blocked for each dependent."""
    # Seed test data
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("task/issue-102", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("task/issue-102", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    temp_store.add_issue_link("task/issue-102", 102, "task")

    github_client = MagicMock()

    # Mock BlockedStateService.reconcile_blocked to return READY
    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService.reconcile_blocked",
        return_value=IssueState.READY,
    ):
        service = DependencyRecheckService(
            store=temp_store, github_client=github_client
        )
        event = IssueResolvedDependency(issue_number=9, merged=True)

        result = service.handle_issue_resolved(event)

        assert result.issue_number == 9
        assert result.dependents_checked == 2
        assert result.unblocked == 2
        assert result.still_blocked == 0
        assert result.errors == 0


def test_handle_issue_resolved_max_dependents_limit(temp_store: SQLiteClient) -> None:
    """Test that service limits dependents to MAX_DEPENDENTS_PER_EVENT."""
    # Seed 30 dependent branches (exceeds limit of 25)
    for i in range(30):
        branch = f"task/issue-{i + 100}"
        temp_store.update_flow_state(branch, flow_status="active")
        temp_store.add_issue_link(branch, 9, "dependency")
        temp_store.add_issue_link(branch, i + 100, "task")

    github_client = MagicMock()

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService.reconcile_blocked",
        return_value=IssueState.READY,
    ):
        service = DependencyRecheckService(
            store=temp_store, github_client=github_client
        )
        event = IssueResolvedDependency(issue_number=9, merged=True)

        result = service.handle_issue_resolved(event)

        # Should only process first 25 dependents
        assert result.dependents_checked == 25
        assert result.unblocked == 25


def test_handle_issue_resolved_error_handling(temp_store: SQLiteClient) -> None:
    """Test that service handles errors gracefully and continues processing."""
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("task/issue-102", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("task/issue-102", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    temp_store.add_issue_link("task/issue-102", 102, "task")

    github_client = MagicMock()

    # Mock reconcile_blocked to raise exception for first branch, succeed for second
    mock_reconcile = MagicMock()
    mock_reconcile.side_effect = [
        RuntimeError("API error"),
        IssueState.READY,
    ]

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService.reconcile_blocked",
        mock_reconcile,
    ):
        service = DependencyRecheckService(
            store=temp_store, github_client=github_client
        )
        event = IssueResolvedDependency(issue_number=9, merged=True)

        result = service.handle_issue_resolved(event)

        assert result.dependents_checked == 2
        assert result.unblocked == 1
        assert result.errors == 1


def test_handle_issue_resolved_missing_issue_number(temp_store: SQLiteClient) -> None:
    """Test that service skips branches without task issue numbers."""
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("feature/no-issue", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("feature/no-issue", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    # feature/no-issue has no task issue link

    github_client = MagicMock()

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService.reconcile_blocked",
        return_value=IssueState.READY,
    ):
        service = DependencyRecheckService(
            store=temp_store, github_client=github_client
        )
        event = IssueResolvedDependency(issue_number=9, merged=True)

        result = service.handle_issue_resolved(event)

        assert result.dependents_checked == 2
        assert result.unblocked == 1  # Only one has issue number
        assert result.still_blocked == 1  # Branch without issue number is skipped
