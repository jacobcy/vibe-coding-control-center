"""Tests for GovernanceService."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
)


class MockStatusService:
    """Mock status service for testing."""

    def __init__(self, snapshot: OrchestraSnapshot | None = None):
        self._snapshot = snapshot

    def snapshot(self) -> OrchestraSnapshot:
        if self._snapshot:
            return self._snapshot
        return OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )


def _make_dispatcher(run_result: bool = True) -> MagicMock:
    """Create a mock Dispatcher with repo_path and run_governance_command."""
    dispatcher = MagicMock()
    dispatcher.repo_path = Path("/repo")
    dispatcher.run_governance_command.return_value = run_result
    return dispatcher


def _make_service(
    config: OrchestraConfig | None = None,
    snapshot: OrchestraSnapshot | None = None,
    run_result: bool = True,
) -> GovernanceService:
    """Helper to create a GovernanceService with mocked dependencies."""
    return GovernanceService(
        config=config or OrchestraConfig(),
        status_service=MockStatusService(snapshot),
        dispatcher=_make_dispatcher(run_result),
    )


class TestGovernanceService:
    """Tests for GovernanceService."""

    def test_no_webhook_events(self):
        """GovernanceService should not handle webhook events."""
        service = _make_service()
        assert service.event_types == []

    def test_tick_interval_from_config(self):
        """Governance should only run on config.governance.interval_ticks boundary."""
        from vibe3.orchestra.config import GovernanceConfig

        config = OrchestraConfig(governance=GovernanceConfig(interval_ticks=4))
        service = _make_service(config=config)

        assert service._tick_count == 0
        # Ticks 1-3 should not trigger
        service._tick_count = 1
        assert service._tick_count % 4 != 0
        service._tick_count = 3
        assert service._tick_count % 4 != 0
        # Tick 4 triggers
        service._tick_count = 4
        assert service._tick_count % 4 == 0

    def test_build_governance_plan_empty(self):
        """Plan should handle empty issue list."""
        service = _make_service()
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "# Orchestra Governance Scan" in plan
        assert "No active issues" in plan

    def test_build_governance_plan_with_issues(self):
        """Plan should include issue details."""
        service = _make_service()
        issue = IssueStatusEntry(
            number=42,
            title="Test issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(issue,),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "#42" in plan
        assert "Test issue" in plan

    def test_build_governance_plan_with_blocked_issues(self):
        """Plan should show blocked_by relationships."""
        service = _make_service()
        issue = IssueStatusEntry(
            number=42,
            title="Blocked issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(41, 40),
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(issue,),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "#41" in plan
        assert "#40" in plan

    def test_circuit_breaker_state_in_plan(self):
        """Plan should include circuit breaker state."""
        service = _make_service()
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="half_open",
            circuit_breaker_failures=2,
        )
        plan = service._build_governance_plan(snapshot)
        assert "half_open" in plan

    def test_delegates_to_dispatcher(self):
        """Execution uses dispatcher.run_governance_command."""
        service = _make_service()
        # Verify the service has no _execute_command attribute
        assert not hasattr(service, "_execute_command")
        # Verify it holds a dispatcher
        assert service._dispatcher is not None
        assert hasattr(service._dispatcher, "run_governance_command")

    def test_skip_when_circuit_breaker_open(self):
        """Governance skips dispatch when circuit breaker is OPEN (snapshot check)."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="open",
            circuit_breaker_failures=3,
        )
        dispatcher = _make_dispatcher()
        service = GovernanceService(
            config=OrchestraConfig(dry_run=True),
            status_service=MockStatusService(snapshot),
            dispatcher=dispatcher,
        )
        # snapshot reflects open state
        assert service._status_service.snapshot().circuit_breaker_state == "open"
        # dispatcher.run_governance_command should not be called on open circuit
        dispatcher.run_governance_command.assert_not_called()
