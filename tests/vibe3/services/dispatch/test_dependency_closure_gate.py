"""Tests for DependencyClosureGate."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.services.dispatch import DependencyClosureGate


def test_notify_downstream_no_dependents(temp_store: SQLiteClient) -> None:
    """Test that gate returns empty list when no dependents found."""
    github_client = MagicMock()

    result = DependencyClosureGate.notify_downstream(
        issue_number=999,
        store=temp_store,
        github_client=github_client,
    )

    assert result == []
    # Should not attempt to post any comments
    github_client.add_comment.assert_not_called()


def test_notify_downstream_posts_comments(temp_store: SQLiteClient) -> None:
    """Test that gate posts advisory comments on downstream issues."""
    # Seed test data
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("task/issue-102", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("task/issue-102", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    temp_store.add_issue_link("task/issue-102", 102, "task")

    github_client = MagicMock()

    result = DependencyClosureGate.notify_downstream(
        issue_number=9,
        store=temp_store,
        github_client=github_client,
    )

    assert result == [101, 102]
    # Should have posted comments on both downstream issues
    assert github_client.add_comment.call_count == 2

    # Verify comment content
    first_call = github_client.add_comment.call_args_list[0]
    assert first_call[0][0] == 101  # issue number
    assert "upstream dependency #9" in first_call[0][1]  # comment body
    assert "audit issue #3229" in first_call[0][1]


def test_notify_downstream_handles_comment_errors(temp_store: SQLiteClient) -> None:
    """Test that gate continues processing when comment posting fails."""
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("task/issue-102", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("task/issue-102", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    temp_store.add_issue_link("task/issue-102", 102, "task")

    github_client = MagicMock()

    # Mock add_comment to fail for first issue, succeed for second
    github_client.add_comment.side_effect = [
        RuntimeError("API error"),  # First comment fails
        None,  # Second succeeds
    ]

    result = DependencyClosureGate.notify_downstream(
        issue_number=9,
        store=temp_store,
        github_client=github_client,
    )

    # Should still return the second issue that succeeded
    assert result == [102]
    assert github_client.add_comment.call_count == 2


def test_notify_downstream_skips_missing_issue_number(
    temp_store: SQLiteClient,
) -> None:
    """Test that gate skips branches without task issue numbers."""
    temp_store.update_flow_state("task/issue-101", flow_status="active")
    temp_store.update_flow_state("feature/no-issue", flow_status="active")
    temp_store.add_issue_link("task/issue-101", 9, "dependency")
    temp_store.add_issue_link("feature/no-issue", 9, "dependency")
    temp_store.add_issue_link("task/issue-101", 101, "task")
    # feature/no-issue has no task issue link

    github_client = MagicMock()

    result = DependencyClosureGate.notify_downstream(
        issue_number=9,
        store=temp_store,
        github_client=github_client,
    )

    assert result == [101]  # Only branch with issue number is notified
    assert github_client.add_comment.call_count == 1
