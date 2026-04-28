"""Tests for flow model migrations."""

from vibe3.models.flow import FlowState


class TestFlowStatusMigration:
    """Tests for flow_status field migration (idle->active, missing->stale)."""

    def test_migrate_idle_to_active(self):
        """Test that 'idle' status is migrated to 'active'."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="idle")
        assert flow.flow_status == "active"

    def test_migrate_missing_to_stale(self):
        """Test that 'missing' status is migrated to 'stale'."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="missing")
        assert flow.flow_status == "stale"

    def test_active_status_unchanged(self):
        """Test that 'active' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="active")
        assert flow.flow_status == "active"

    def test_blocked_status_migrated_to_active(self):
        """Test that 'blocked' status is migrated to 'active'.

        Blocked/failed removed from flow_status (2026-04-28).
        Blocked status is now inferred from IssueState.BLOCKED label.
        """
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="blocked")
        assert flow.flow_status == "active"

    def test_failed_status_migrated_to_active(self):
        """Test that 'failed' status is migrated to 'active'.

        Failed unified to blocked (2026-04-28).
        """
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="failed")
        assert flow.flow_status == "active"

    def test_done_status_unchanged(self):
        """Test that 'done' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="done")
        assert flow.flow_status == "done"

    def test_stale_status_unchanged(self):
        """Test that 'stale' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="stale")
        assert flow.flow_status == "stale"
