"""Tests for issue failure/block side effects with flow state integration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.flow.service import FlowService
from vibe3.services.issue.failure import (
    block_manager_noop_issue,
    fail_manager_issue,
)


def test_fail_manager_issue_records_to_error_log_only():
    """Test fail_manager_issue records to error_log only (no blocked_reason)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-100"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-100", branch=branch, actor="test-user")
        store.add_issue_link(branch, 100, "task")

        with patch(
            "vibe3.services.issue.failure._get_issue_flow_service"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            fail_manager_issue(
                issue_number=100,
                reason="Test manager failure",
                actor="agent:manager",
            )

        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] is None
        assert flow_state["flow_status"] == "active"

        events = store.get_events(branch)
        failed_events = [e for e in events if e.get("event_type") == "flow_failed"]
        assert len(failed_events) >= 1
        assert "Test manager failure" in failed_events[0].get("detail", "")


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
            "vibe3.services.issue.failure._get_issue_flow_service"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            with patch(
                "vibe3.services.flow.timeline.FlowTimelineService"
            ) as mock_timeline_class:
                mock_timeline = MagicMock()
                mock_timeline_class.return_value = mock_timeline

                with patch(
                    "vibe3.services.shared.label_service.LabelService"
                ) as mock_label_service_class:
                    mock_label_service = MagicMock()
                    mock_label_service_class.return_value = mock_label_service

                    with patch(
                        "vibe3.services.blocked_state_io.GitHubClient"
                    ) as mock_github_class:
                        mock_github = MagicMock()
                        mock_github.get_issue_body.return_value = "User content"
                        mock_github_class.return_value = mock_github

                        block_manager_noop_issue(
                            issue_number=200,
                            repo=None,
                            reason="No progress made",
                            actor="agent:manager",
                        )

        # Verify reason recorded in flow and flow_status set to blocked
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] == "No progress made"
        assert flow_state["flow_status"] == "blocked"


def test_block_flow_uses_new_fields():
    """Test block_flow writes blocked_by_issue + blocked_reason (new fields).

    Note: flow_status no longer set to "blocked" (2026-04-28).
    Blocked status inferred from IssueState.BLOCKED label.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-300"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-300", branch=branch, actor="test-user")
        store.add_issue_link(branch, 300, "task")

        with patch("vibe3.services.blocked_state_io.GitHubClient") as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_issue_body.return_value = "User content"
            mock_github_class.return_value = mock_github

            # Block flow with dependency issue
            flow_service.block_flow(
                branch,
                reason="Blocked by dependency",
                blocked_by_issue=301,
                actor="test-actor",
            )

        # Verify flow state in database (blocked metadata, NOT flow_status)
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_by_issue"] == 301
        assert flow_state["blocked_reason"] == "Blocked by dependency"

        # Verify event was recorded
        events = store.get_events(branch)
        blocked_events = [e for e in events if e.get("event_type") == "flow_blocked"]
        assert len(blocked_events) >= 1


def test_block_flow_writes_body_label_and_cache():
    """Regression: block_flow(reason) writes body projection + label + local cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-400"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-400", branch=branch, actor="test-user")
        store.add_issue_link(branch, 400, "task")

        with patch(
            "vibe3.services.shared.label_service.LabelService"
        ) as mock_label_cls:
            mock_label = MagicMock()
            mock_label_cls.return_value = mock_label

            with patch(
                "vibe3.services.flow.timeline.FlowTimelineService"
            ) as mock_timeline_cls:
                mock_timeline = MagicMock()
                mock_timeline_cls.return_value = mock_timeline

                with patch(
                    "vibe3.services.blocked_state_io.GitHubClient"
                ) as mock_github_class:
                    mock_github = MagicMock()
                    mock_github.get_issue_body.return_value = "User content"
                    mock_github_class.return_value = mock_github

                    flow_service.block_flow(
                        branch,
                        reason="Health check failed: worktree missing",
                        actor="orchestra:dispatcher",
                    )

        # Local cache
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] == "Health check failed: worktree missing"

        # Label transition called via confirm_issue_state
        mock_label.confirm_issue_state.assert_called_once()


def test_fail_issue_records_to_error_log_only():
    """Test fail_manager_issue records to error_log only (no block_flow)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        branch = "task/issue-500"
        flow_service = FlowService(store=store)
        flow_service.create_flow(slug="issue-500", branch=branch, actor="test-user")
        store.add_issue_link(branch, 500, "task")

        with patch("vibe3.services.issue.failure._get_issue_flow_service") as mock_ifs:
            mock_issue_flow = MagicMock()
            mock_issue_flow.store = store
            mock_ifs.return_value = mock_issue_flow

            fail_manager_issue(
                issue_number=500,
                reason="Manager cycle exhausted",
                actor="agent:manager",
            )

        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] is None
        assert flow_state["flow_status"] == "active"

        events = store.get_events(branch)
        failed_events = [e for e in events if e.get("event_type") == "flow_failed"]
        assert len(failed_events) >= 1
        assert "Manager cycle exhausted" in failed_events[0].get("detail", "")


def test_block_manager_noop_issue_no_flow():
    """block_manager_noop_issue() should return early if no flow exists."""
    with patch(
        "vibe3.services.issue.failure._get_issue_flow_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_store = MagicMock()
        mock_service.store = mock_store
        mock_get_service.return_value = mock_service

        # No flow found
        mock_store.get_flows_by_issue.return_value = []

        with patch("vibe3.services.FlowService") as mock_flow_service:
            block_manager_noop_issue(
                issue_number=123, repo=None, reason="Test reason", actor="test:actor"
            )

            # Should NOT call block_flow
            mock_flow_service.return_value.block_flow.assert_not_called()
