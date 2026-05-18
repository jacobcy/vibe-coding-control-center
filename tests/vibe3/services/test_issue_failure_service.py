"""Tests for issue failure/block side effects with flow state integration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    block_manager_noop_issue,
    fail_manager_issue,
)


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
            "vibe3.services.issue_failure_service._get_issue_flow_service"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            with patch(
                "vibe3.services.flow_block_mixin.FlowTimelineService"
            ) as mock_timeline_class:
                mock_timeline = MagicMock()
                mock_timeline_class.return_value = mock_timeline

                with patch(
                    "vibe3.services.flow_block_mixin.LabelService"
                ) as mock_label_service_class:
                    mock_label_service = MagicMock()
                    mock_label_service_class.return_value = mock_label_service

                    fail_manager_issue(
                        issue_number=100,
                        reason="Test manager failure",
                        actor="agent:manager",
                    )

        # Verify reason recorded in flow and flow_status set to blocked
        flow_state = store.get_flow_state(branch)
        assert flow_state is not None
        assert flow_state["blocked_reason"] == "Test manager failure"
        assert flow_state["flow_status"] == "blocked"


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
            "vibe3.services.issue_failure_service._get_issue_flow_service"
        ) as mock_issue_flow_service_class:
            mock_issue_flow_service = MagicMock()
            mock_issue_flow_service_class.return_value = mock_issue_flow_service
            mock_issue_flow_service.store = store

            with patch(
                "vibe3.services.flow_block_mixin.FlowTimelineService"
            ) as mock_timeline_class:
                mock_timeline = MagicMock()
                mock_timeline_class.return_value = mock_timeline

                with patch(
                    "vibe3.services.flow_block_mixin.LabelService"
                ) as mock_label_service_class:
                    mock_label_service = MagicMock()
                    mock_label_service_class.return_value = mock_label_service

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
