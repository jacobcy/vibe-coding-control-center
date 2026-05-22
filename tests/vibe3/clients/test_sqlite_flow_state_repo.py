"""Tests for SQLite flow state repository."""

import tempfile
from pathlib import Path

from vibe3.clients.sqlite_client import SQLiteClient


def test_soft_delete_flow_normalizes_to_tombstone() -> None:
    """Test that soft_delete_flow clears refs and sets aborted status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create a flow with active metadata
        store.update_flow_state(
            "task/issue-123",
            flow_slug="issue_123",
            flow_status="active",
            spec_ref="#123",
            plan_ref="docs/plans/test.md",
            report_ref="docs/reports/test.md",
            audit_ref="docs/audits/test.md",
            indicate_ref="docs/indicate/test.md",
            pr_ref="https://github.com/test/pr/456",
            blocked_reason="API design pending",
            failed_reason="Test failure",
            blocked_by_issue=789,
            worktree_path="/tmp/worktree-123",
            planner_actor="claude/sonnet-4.6",
            executor_actor="claude/sonnet-4.6",
            reviewer_actor="claude/sonnet-4.6",
            manager_actor="vibe-manager-agent",
            latest_actor="claude/sonnet-4.6",
        )

        # Soft delete the flow
        store.soft_delete_flow("task/issue-123")

        # Verify tombstone state (must read including deleted)
        deleted_flow = store.get_flow_state_include_deleted("task/issue-123")
        assert deleted_flow is not None

        # CRITICAL: flow_status must be 'aborted' (terminal state)
        assert deleted_flow["flow_status"] == "aborted"

        # CRITICAL: all refs must be cleared
        assert deleted_flow["spec_ref"] is None
        assert deleted_flow["plan_ref"] is None
        assert deleted_flow["report_ref"] is None
        assert deleted_flow["audit_ref"] is None
        assert deleted_flow["indicate_ref"] is None
        assert deleted_flow["pr_ref"] is None

        # CRITICAL: reasons and blocked_by must be cleared
        assert deleted_flow["blocked_reason"] is None
        assert deleted_flow["failed_reason"] is None
        assert deleted_flow["blocked_by_issue"] is None

        # CRITICAL: worktree_path must be cleared
        assert deleted_flow["worktree_path"] is None

        # CRITICAL: deleted_at must be set
        assert deleted_flow["deleted_at"] is not None

        # Actor fields should be cleared (no active runtime attribution)
        assert deleted_flow["planner_actor"] is None
        assert deleted_flow["executor_actor"] is None
        assert deleted_flow["reviewer_actor"] is None
        assert deleted_flow["manager_actor"] is None
        assert deleted_flow["latest_actor"] is None

        # CRITICAL: execution state fields must be cleared
        assert deleted_flow["planner_status"] is None
        assert deleted_flow["executor_status"] is None
        assert deleted_flow["reviewer_status"] is None
        assert deleted_flow["execution_pid"] is None
        assert deleted_flow["execution_started_at"] is None
        assert deleted_flow["execution_completed_at"] is None
        assert deleted_flow["next_step"] is None

        # CRITICAL: legacy blocked_by must be cleared
        assert deleted_flow["blocked_by"] is None


def test_soft_delete_flow_clears_refs_from_active_flow() -> None:
    """Test that refs are cleared when deleting active flow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow with all refs populated
        store.update_flow_state(
            "dev/issue-456",
            flow_slug="issue_456",
            plan_ref="docs/plans/feature.md",
            report_ref="docs/reports/feature.md",
            audit_ref="docs/audits/feature.md",
        )

        store.soft_delete_flow("dev/issue-456")

        deleted = store.get_flow_state_include_deleted("dev/issue-456")
        assert deleted is not None
        assert deleted["plan_ref"] is None
        assert deleted["report_ref"] is None
        assert deleted["audit_ref"] is None
