"""Tests for TickPlanner service."""

from unittest.mock import MagicMock

from vibe3.models.tick import TickPhase, TickRequest, TickSource
from vibe3.services.tick_planner import TickPlanner


class TestTickPlanner:
    """Tests for TickPlanner service."""

    def test_planner_resolves_governance_material(self):
        """Test planner auto-selects governance material when not specified."""
        # Mock config
        mock_config = MagicMock()

        # Create request without explicit material
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[TickPhase.GOVERNANCE],
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        # Plan should have governance enabled
        assert plan.governance_enabled is True
        # Material should be None (auto-selection happens in TickPlan.from_request)
        # which calls _resolve_governance_material
        assert plan.governance_material is not None  # Should be resolved

    def test_planner_uses_explicit_material(self):
        """Test planner uses explicit material when provided."""
        mock_config = MagicMock()

        # Create request with explicit material
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[TickPhase.GOVERNANCE],
            governance_material="explicit-material",
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        assert plan.governance_enabled is True
        assert plan.governance_material == "explicit-material"

    def test_planner_scans_supervisor_candidates(self):
        """Test planner creates plan with empty issues list when no explicit issues."""
        mock_config = MagicMock()

        # Create request without explicit issues
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[TickPhase.SUPERVISOR],
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        # Plan should have supervisor enabled
        assert plan.supervisor_enabled is True
        # Issues should be empty (scanning happens during dispatch)
        assert plan.supervisor_issues == []

    def test_planner_uses_explicit_issues(self):
        """Test planner uses explicit issue numbers when provided."""
        mock_config = MagicMock()

        # Create request with explicit issues
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[TickPhase.SUPERVISOR],
            supervisor_issue_numbers=[123, 456],
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        assert plan.supervisor_enabled is True
        assert plan.supervisor_issues == [123, 456]

    def test_planner_respects_phase_disable(self):
        """Test planner respects phase enable/disable flags."""
        mock_config = MagicMock()

        # Create request with both phases disabled
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[],  # No phases
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        assert plan.governance_enabled is False
        assert plan.governance_material is None
        assert plan.supervisor_enabled is False
        assert plan.supervisor_issues == []

    def test_planner_handles_dry_run(self):
        """Test planner passes through dry_run flag."""
        mock_config = MagicMock()

        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            dry_run=True,
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=0)

        assert plan.dry_run is True

    def test_planner_handles_heartbeat_source(self):
        """Test planner works with heartbeat source."""
        mock_config = MagicMock()

        request = TickRequest(
            source=TickSource.HEARTBEAT,
            tick_id=5,
            phases=[TickPhase.GOVERNANCE, TickPhase.SUPERVISOR],
        )

        planner = TickPlanner(mock_config)
        plan = planner.plan(request, tick_count=5)

        assert plan.governance_enabled is True
        assert plan.supervisor_enabled is True
        assert plan.dry_run is False

    def test_planner_stores_config(self):
        """Test planner stores config as instance variable."""
        mock_config = MagicMock()

        planner = TickPlanner(mock_config)
        assert planner.config is mock_config

    def test_planner_with_none_config(self):
        """Test planner handles None config (for testing)."""
        # None config should work (for testing scenarios)
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            tick_id=0,
            phases=[TickPhase.GOVERNANCE],
        )

        planner = TickPlanner(None)
        plan = planner.plan(request, tick_count=0)

        # Should work but material will be None (no auto-selection)
        assert plan.governance_enabled is True
        assert plan.governance_material is None
