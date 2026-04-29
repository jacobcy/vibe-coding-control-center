"""Tests for flow lifecycle integrity through FlowService."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.exceptions import UserError
from vibe3.services.flow_service import FlowService


def test_reactivate_flow_records_event():
    """Flow reactivation should record a 'flow_reactivated' event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from vibe3.clients.sqlite_client import SQLiteClient

        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        service = FlowService(store=store)

        # Create a flow first
        branch = "task/issue-123"
        slug = "issue-123"
        service.create_flow(slug=slug, branch=branch, actor="test-user")

        # Reactivate the flow
        result = service.reactivate_flow(
            branch, flow_slug=slug, initiator="test-initiator"
        )

        assert result.flow_slug == slug
        assert result.flow_status == "active"
        # session_id fields are no longer in the model
        # (registry is the source of truth)
        assert result.plan_ref is None
        assert result.report_ref is None
        assert result.audit_ref is None

        # Verify event was recorded
        events = store.get_events(branch)
        assert len(events) >= 2  # flow_created + flow_reactivated

        reactivated_events = [
            e for e in events if e.get("event_type") == "flow_reactivated"
        ]
        assert len(reactivated_events) == 1
        assert reactivated_events[0].get("detail") == "Flow reactivated"


def test_reactivate_flow_resets_all_sessions():
    """Reactivation should clear all agent actors and refs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from vibe3.clients.sqlite_client import SQLiteClient

        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        service = FlowService(store=store)

        # Create and manually set actors and refs
        branch = "task/issue-456"
        service.create_flow(slug="issue-456", branch=branch)
        store.update_flow_state(
            branch,
            planner_actor="old-planner",
            executor_actor="old-executor",
            reviewer_actor="old-reviewer",
            latest_actor="old-latest",
            plan_ref="plans/old-plan.md",
            report_ref="reports/old-report.md",
            audit_ref="audits/old-audit.md",
        )

        # Reactivate
        service.reactivate_flow(branch)

        # Verify all actors and refs cleared
        state = store.get_flow_state(branch)
        assert state is not None
        assert state.get("latest_actor") is None
        assert state.get("planner_actor") is None
        assert state.get("executor_actor") is None
        assert state.get("reviewer_actor") is None
        # session_id fields are no longer tracked in flow_state
        # (registry is the source of truth)
        assert state.get("plan_ref") is None
        assert state.get("report_ref") is None
        assert state.get("audit_ref") is None


def test_reactivate_flow_preserves_initiator():
    """Reactivation should set initiated_by correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from vibe3.clients.sqlite_client import SQLiteClient

        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        service = FlowService(store=store)

        branch = "task/issue-789"
        service.create_flow(slug="issue-789", branch=branch)

        # Reactivate with explicit initiator
        service.reactivate_flow(branch, initiator="explicit-initiator")

        state = store.get_flow_state(branch)
        assert state is not None
        assert state.get("initiated_by") == "explicit-initiator"


def test_flow_manager_uses_service_for_reactivation():
    """FlowManager should delegate to FlowService for reactivation."""
    from vibe3.execution.flow_dispatch import FlowManager
    from vibe3.models.orchestra_config import OrchestraConfig

    config = OrchestraConfig(repo="test/repo")
    manager = FlowManager(config)

    # Mock the flow service
    manager.flow_service.reactivate_flow = MagicMock(
        return_value=MagicMock(
            model_dump=lambda: {"branch": "task/issue-999", "flow_slug": "issue-999"}
        )
    )

    from vibe3.models.orchestration import IssueInfo

    issue = IssueInfo(number=999, title="Test", labels=[])
    result = manager._reactivate_canonical_flow(issue, "task/issue-999", "issue-999")

    # Verify service was called
    manager.flow_service.reactivate_flow.assert_called_once()
    call_kwargs = manager.flow_service.reactivate_flow.call_args[1]
    assert call_kwargs["flow_slug"] == "issue-999"
    # initiator is resolved by SignatureService
    assert "initiator" in call_kwargs

    # Verify result is dict (from model_dump())
    assert result["branch"] == "task/issue-999"


def test_reactivate_flow_rejects_nonexistent_flow():
    """Reactivate should fail if flow doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from vibe3.clients.sqlite_client import SQLiteClient

        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        service = FlowService(store=store)

        # Try to reactivate a flow that was never created
        branch = "task/issue-999"
        with pytest.raises(UserError, match="Flow not found"):
            service.reactivate_flow(branch, flow_slug="issue-999")

        # Also test with no flow_slug provided
        with pytest.raises(UserError, match="Flow not found"):
            service.reactivate_flow(branch)
