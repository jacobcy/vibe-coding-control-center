"""Tests for coordination resolver."""

from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.models.data_source import DataSource
from vibe3.services.coordination_resolver import CoordinationResolver


def test_resolve_coordination_remote_first():
    """Test coordination resolver prefers remote over local."""
    store = MagicMock(spec=SQLiteClient)
    store.get_flow_state.return_value = {
        "blocked_reason": "Local reason",
        "blocked_by_issue": 111,
        "worktree_path": "/tmp/wt",
        "latest_actor": "claude/sonnet-4.6",
    }
    store.get_dependency_links.return_value = [999]

    resolver = CoordinationResolver(store=store)

    with patch(
        "vibe3.services.coordination_resolver.CoordinationResolver._read_remote_collaboration"
    ) as mock_remote:
        mock_remote.return_value = {
            "blocked_reason": "Remote reason",
            "blocked_by_issue": 222,
            "dependencies": [123, 456],
        }

        truth = resolver.resolve_coordination(
            branch="dev/issue-946",
            issue_number=946,
        )

        # Remote data takes precedence
        assert truth.blocked_reason == "Remote reason"
        assert truth.blocked_reason_source == DataSource.ISSUE_BODY_FALLBACK
        assert truth.blocked_by_issue == 222
        assert truth.blocked_by_issue_source == DataSource.ISSUE_BODY_FALLBACK
        assert truth.dependencies == [123, 456]

        # Execution fields from local
        assert truth.worktree_path == "/tmp/wt"
        assert truth.actor == "claude/sonnet-4.6"


def test_resolve_coordination_fallback_to_local():
    """Test resolver falls back to local when remote unavailable."""
    store = MagicMock(spec=SQLiteClient)
    store.get_flow_state.return_value = {
        "blocked_reason": "Local block",
        "blocked_by_issue": 333,
        "latest_actor": "orchestra:manager",
    }
    store.get_dependency_links.return_value = [789]

    resolver = CoordinationResolver(store=store)

    # Simulate remote read failure
    with patch(
        "vibe3.services.coordination_resolver.CoordinationResolver._read_remote_collaboration"
    ) as mock_remote:
        mock_remote.return_value = None

        truth = resolver.resolve_coordination(
            branch="dev/issue-946",
            issue_number=946,
        )

        # Local data used when remote unavailable
        assert truth.blocked_reason == "Local block"
        assert truth.blocked_reason_source == DataSource.LOCAL_SQLITE
        assert truth.blocked_by_issue == 333
        assert truth.dependencies == [789]


def test_resolve_coordination_no_issue_number():
    """Test resolver uses local-only when no issue number."""
    store = MagicMock(spec=SQLiteClient)
    store.get_flow_state.return_value = {
        "blocked_reason": "Local only",
    }

    resolver = CoordinationResolver(store=store)

    truth = resolver.resolve_coordination(
        branch="dev/issue-946",
        issue_number=None,  # No remote possible
    )

    assert truth.blocked_reason == "Local only"
    assert truth.blocked_reason_source == DataSource.LOCAL_SQLITE
