"""Tests for issue failure/block side effects with flow state integration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    _ensure_flow_state_for_issue,
    block_manager_noop_issue,
    fail_manager_issue,
)


def test_ensure_flow_state_for_issue_existing_flow_block():
    """Test helper finds existing flow and records blocked_reason
    (no flow_status change)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow manually
        branch = "task/issue-123"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-123", branch=branch, actor="test-user")

        # Link issue so get_flows_by_issue returns it
        store.add_issue_link(branch, 123, "task")

        # Mock IssueFlowService to expose the real store
        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            _ensure_flow_state_for_issue(123, "block", "Test reason", "test-actor")

        # Verify blocked_reason was recorded
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] == "Test reason"
        # flow_status must NOT be changed — GitHub labels are the SSOT
        assert flow_state["flow_status"] == "active"


def test_ensure_flow_state_for_issue_existing_flow_fail():
    """Test helper finds existing flow and records failed_reason
    (no flow_status change)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-456"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-456", branch=branch, actor="test-user")
        store.add_issue_link(branch, 456, "task")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            _ensure_flow_state_for_issue(456, "fail", "Test failure", "test-actor")

        # Verify failed_reason was recorded
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["failed_reason"] == "Test failure"
        # flow_status must NOT be changed — GitHub labels are the SSOT
        assert flow_state["flow_status"] == "active"


def test_ensure_flow_state_for_issue_no_flow_is_noop():
    """Test helper silently returns when no flow exists (no minimal flow creation)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            # No flows exist for issue 789 — should return silently
            _ensure_flow_state_for_issue(789, "block", "No flow test", "test-actor")

        # Nothing should have been written
        store2 = SQLiteClient(db_path=str(db_path))
        flows = store2.get_flows_by_issue(789, role="task")
        assert flows == [], "Should not create minimal flows"


def test_ensure_flow_state_for_issue_fallback_on_error():
    """Test non-blocking: store write failure should not raise."""
    with patch(
        "vibe3.services.issue_failure_service.IssueFlowService"
    ) as mock_issue_flow_service_class:
        mock_issue_flow_service = MagicMock()
        mock_issue_flow_service_class.return_value = mock_issue_flow_service
        mock_store = MagicMock()
        mock_issue_flow_service.store = mock_store
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-999", "flow_slug": "issue-999"}
        ]
        # Simulate store write failure
        mock_store.update_flow_state.side_effect = Exception("DB write failed")

        # Call helper - should not raise, should log warning and continue
        _ensure_flow_state_for_issue(999, "block", "Fallback test", "test-actor")

        # Verify update was attempted
        mock_store.update_flow_state.assert_called_once()


def test_fail_manager_issue_records_reason_and_syncs_github():
    """Test fail_manager_issue records reason on flow AND applies GitHub state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-100"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-100", branch=branch, actor="test-user")
        store.add_issue_link(branch, 100, "task")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            with patch(
                "vibe3.services.issue_failure_service.GitHubClient"
            ) as mock_github_class:
                mock_github = MagicMock()
                mock_github_class.return_value = mock_github

                with patch(
                    "vibe3.services.issue_failure_service.LabelService"
                ) as mock_label_service_class:
                    mock_label_service = MagicMock()
                    mock_label_service_class.return_value = mock_label_service

                    fail_manager_issue(
                        issue_number=100,
                        reason="Test manager failure",
                        actor="agent:manager",
                    )

                    # Verify GitHub sync happened
                    mock_label_service.confirm_issue_state.assert_called_once()

        # Verify reason recorded in flow (not changing flow_status)
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["failed_reason"] == "Test manager failure"
        assert flow_state["flow_status"] == "active"


def test_block_manager_noop_issue_records_reason_and_syncs_github():
    """Test block_manager_noop_issue records reason on flow AND applies GitHub state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-200"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-200", branch=branch, actor="test-user")
        store.add_issue_link(branch, 200, "task")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            with patch(
                "vibe3.services.issue_failure_service.GitHubClient"
            ) as mock_github_class:
                mock_github = MagicMock()
                mock_github_class.return_value = mock_github

                with patch(
                    "vibe3.services.issue_failure_service.LabelService"
                ) as mock_label_service_class:
                    mock_label_service = MagicMock()
                    mock_label_service_class.return_value = mock_label_service

                    block_manager_noop_issue(
                        issue_number=200,
                        repo=None,
                        reason="No progress made",
                        actor="agent:manager",
                    )

                    # Verify GitHub sync happened
                    mock_label_service.confirm_issue_state.assert_called_once()

        # Verify reason recorded in flow (not changing flow_status)
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] == "No progress made"
        assert flow_state["flow_status"] == "active"


def test_block_flow_uses_new_fields():
    """Test block_flow writes blocked_by_issue + blocked_reason (new fields)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-300"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-300", branch=branch, actor="test-user")

        # Block flow with dependency issue
        flow_service.block_flow(
            branch,
            reason="Blocked by dependency",
            blocked_by_issue=301,
            actor="test-actor",
        )

        # Verify flow state in database
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["flow_status"] == "blocked"
        assert flow_state["blocked_by_issue"] == 301
        assert flow_state["blocked_reason"] == "Blocked by dependency"

        # Verify event was recorded
        events = store.get_events(branch)
        blocked_events = [e for e in events if e.get("event_type") == "flow_blocked"]
        assert len(blocked_events) >= 1
