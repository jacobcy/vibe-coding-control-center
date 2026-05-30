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

    def test_blocked_status_unchanged(self):
        """Test that 'blocked' status is not modified.

        Blocked restored for remote sync semantics (2026-05-17).
        Blocked state is tracked in flow_status for remote synchronization.
        """
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="blocked")
        assert flow.flow_status == "blocked"

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


class TestFlowStatusResponse:
    """Tests for FlowStatusResponse data_source field (merged from test_flow.py)."""

    def test_flow_status_response_has_data_source_field(self):
        """FlowStatusResponse includes data_source for provenance tracking."""
        from vibe3.models.data_source import DataSource
        from vibe3.models.flow import FlowStatusResponse

        response = FlowStatusResponse(
            branch="dev/issue-123",
            flow_slug="issue-123",
            flow_status="active",
            data_source=DataSource.LOCAL_SQLITE,
        )
        assert response.data_source == DataSource.LOCAL_SQLITE

    def test_flow_status_response_data_source_optional(self):
        """data_source is optional (None for backward compatibility)."""
        from vibe3.models.flow import FlowStatusResponse

        response = FlowStatusResponse(
            branch="dev/issue-123",
            flow_slug="issue-123",
            flow_status="active",
        )
        assert response.data_source is None


class TestOrchestraConfigMapping:
    """Tests for orchestra config mapping (merged from test_orchestra_config.py)."""

    def test_from_settings_maps_supervisor_prompt_template(self) -> None:
        from unittest.mock import patch

        from vibe3.config import VibeConfig, load_orchestra_config

        settings = VibeConfig.get_defaults()
        settings.orchestra.supervisor_handoff.prompt_template = (
            "orchestra.supervisor.apply"
        )

        with patch(
            "vibe3.config.settings.VibeConfig.get_defaults", return_value=settings
        ):
            config = load_orchestra_config()

        assert config.supervisor_handoff.prompt_template == "orchestra.supervisor.apply"

    def test_orchestra_config_default_retry_budget_is_three(self) -> None:
        """Default retry budget should be 3 (not 20) to fail fast on stuck entries."""
        from unittest.mock import patch

        from vibe3.config import VibeConfig, load_orchestra_config

        settings = VibeConfig.get_defaults()

        with patch(
            "vibe3.config.settings.VibeConfig.get_defaults", return_value=settings
        ):
            config = load_orchestra_config()

        assert config.max_retry_budget == 3
