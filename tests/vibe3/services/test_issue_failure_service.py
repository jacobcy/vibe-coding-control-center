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
    """Test helper finds existing flow and writes blocked state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow manually
        branch = "task/issue-123"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-123", branch=branch, actor="test-user")

        # Mock IssueFlowService to return the flow
        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = {
                "branch": branch,
                "flow_slug": "issue-123",
            }
            mock_issue_flow_service.canonical_branch_name.return_value = branch

            # Mock FlowService
            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service

                # Call helper
                _ensure_flow_state_for_issue(123, "block", "Test reason", "test-actor")

                # Verify block_flow was called
                mock_flow_service.block_flow.assert_called_once_with(
                    branch, reason="Test reason", actor="test-actor"
                )


def test_ensure_flow_state_for_issue_existing_flow_fail():
    """Test helper finds existing flow and writes failed state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-456"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-456", branch=branch, actor="test-user")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = {
                "branch": branch,
                "flow_slug": "issue-456",
            }
            mock_issue_flow_service.canonical_branch_name.return_value = branch

            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service

                _ensure_flow_state_for_issue(456, "fail", "Test failure", "test-actor")

                # Verify fail_flow was called
                mock_flow_service.fail_flow.assert_called_once_with(
                    branch, reason="Test failure", actor="test-actor"
                )


def test_ensure_flow_state_for_issue_creates_minimal_flow():
    """Test helper creates minimal flow when no flow exists."""
    with tempfile.TemporaryDirectory():
        # Store not needed for this test - mocking FlowService

        branch = "task/issue-789"

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = (
                None  # No existing flow
            )
            mock_issue_flow_service.canonical_branch_name.return_value = branch

            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service

                _ensure_flow_state_for_issue(789, "block", "No flow test", "test-actor")

                # Verify create_flow was called (minimal flow creation)
                mock_flow_service.create_flow.assert_called_once_with(
                    slug="issue-789", branch=branch, actor="test-actor"
                )

                # Verify block_flow was called after creation
                mock_flow_service.block_flow.assert_called_once_with(
                    branch, reason="No flow test", actor="test-actor"
                )


def test_ensure_flow_state_for_issue_fallback_on_error():
    """Test Fallback strategy: continue even if flow write fails."""
    with tempfile.TemporaryDirectory():
        # Store not needed for this test - mocking FlowService

        branch = "task/issue-999"

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = {
                "branch": branch,
                "flow_slug": "issue-999",
            }

            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service
                # Simulate flow write failure
                mock_flow_service.block_flow.side_effect = Exception("DB write failed")

                # Call helper - should not raise, should log and continue
                _ensure_flow_state_for_issue(
                    999, "block", "Fallback test", "test-actor"
                )

                # Verify block_flow was attempted
                mock_flow_service.block_flow.assert_called_once()


def test_fail_manager_issue_calls_ensure_flow_state():
    """Test fail_manager_issue calls helper before GitHub sync."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-100"

        # Create flow manually
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-100", branch=branch, actor="test-user")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = {
                "branch": branch,
                "flow_slug": "issue-100",
            }
            mock_issue_flow_service.canonical_branch_name.return_value = branch

            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service

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

                        # Call fail_manager_issue
                        fail_manager_issue(
                            issue_number=100,
                            reason="Test manager failure",
                            actor="agent:manager",
                        )

                        # Verify flow write happened before GitHub sync
                        mock_flow_service.fail_flow.assert_called_once()

                        # Verify GitHub sync happened after
                        mock_label_service.confirm_issue_state.assert_called_once()


def test_block_manager_noop_issue_calls_ensure_flow_state():
    """Test block_manager_noop_issue calls helper before GitHub sync."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-200"

        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-200", branch=branch, actor="test-user")

        with patch(
            "vibe3.services.issue_failure_service.IssueFlowService"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.find_active_flow.return_value = {
                "branch": branch,
                "flow_slug": "issue-200",
            }
            mock_issue_flow_service.canonical_branch_name.return_value = branch

            with patch(
                "vibe3.services.issue_failure_service.FlowService"
            ) as mock_flow_service_class:
                mock_flow_service = MagicMock()
                mock_flow_service_class.return_value = mock_flow_service

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

                        # Call block_manager_noop_issue
                        block_manager_noop_issue(
                            issue_number=200,
                            repo=None,
                            reason="No progress made",
                            actor="agent:manager",
                        )

                        # Verify flow write happened before GitHub sync
                        mock_flow_service.block_flow.assert_called_once()

                        # Verify GitHub sync happened after
                        mock_label_service.confirm_issue_state.assert_called_once()


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
