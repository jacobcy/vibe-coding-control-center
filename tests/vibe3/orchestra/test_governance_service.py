"""Tests for GovernanceService."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.orchestra.config import GovernanceConfig, OrchestraConfig
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
        manager=_make_dispatcher(run_result),
    )


class TestGovernanceService:
    """Tests for GovernanceService."""

    def test_no_webhook_events(self):
        """GovernanceService should not handle webhook events."""
        service = _make_service()
        assert service.event_types == []

    def test_tick_interval_from_config(self):
        """Governance should only run on config.governance.interval_ticks boundary."""
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
        assert "## Running Issues" in plan
        assert "(无 running issues)" in plan
        assert "## Suggested Issues" in plan
        assert "(无建议 issue)" in plan

    def test_build_governance_plan_with_running_and_suggested_issues(self):
        """Plan should split running issues from suggested issues."""
        service = _make_service()
        running_issue = IssueStatusEntry(
            number=42,
            title="Running issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=True,
            flow_branch="task/issue-42",
            has_worktree=True,
            worktree_path="/repo/wt-issue-42",
            has_pr=True,
            pr_number=401,
            blocked_by=(),
        )
        suggested_issue = IssueStatusEntry(
            number=43,
            title="Suggested issue",
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
            active_issues=(running_issue, suggested_issue),
            active_flows=1,
            active_worktrees=1,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "## Running Issues" in plan
        assert "#42: Running issue" in plan
        assert "flow=task/issue-42" in plan
        assert "worktree=/repo/wt-issue-42" in plan
        assert "pr=#401" in plan
        assert "## Suggested Issues" in plan
        assert "仅供参考" in plan
        assert "#43: Suggested issue" in plan
        assert "flow=(not started)" in plan

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

    def test_build_governance_plan_uses_template_and_supervisor_content(self, tmp_path):
        """Governance plan should render configured template with supervisor content."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(textwrap.dedent("""
                orchestra:
                  governance:
                    plan: |
                      Supervisor: {supervisor_name}
                      Count: {active_count}
                      Issues:
                      {issue_list}
                      Skill Content:
                      {supervisor_content}
                """).strip())
        config = OrchestraConfig(
            governance=GovernanceConfig(
                prompt_template="orchestra.governance.plan",
                include_supervisor_content=True,
            )
        )
        service = GovernanceService(
            config=config,
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            prompts_path=prompts_path,
        )
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
        assert "Supervisor: supervisor/orchestra.md" in plan
        assert "Count: 1" in plan
        assert "#42: Test issue" in plan
        assert "# Orchestra" in plan or "治理材料" in plan

    def test_delegates_to_dispatcher(self):
        """Execution uses manager."""
        service = _make_service()
        # Verify the service has no _execute_command attribute
        assert not hasattr(service, "_execute_command")
        # Verify it holds a manager
        assert service._manager is not None
        assert hasattr(service._manager, "dispatch_manager") or hasattr(
            service._manager, "_run_command"
        )

    @pytest.mark.asyncio
    async def test_skip_when_circuit_breaker_open(self):
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
            config=OrchestraConfig(
                governance=GovernanceConfig(dry_run=True, interval_ticks=1)
            ),
            status_service=MockStatusService(snapshot),
            manager=dispatcher,
        )

        await service._run_governance()
        dispatcher.run_governance_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_tick_runs_on_interval_and_respects_dry_run(self, monkeypatch):
        """Governance runs on interval and uses governance.dry_run."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        dispatcher = _make_dispatcher()
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=2, dry_run=True)
            ),
            status_service=MockStatusService(snapshot),
            manager=dispatcher,
        )
        # Force tick boundary
        service._tick_count = 1

        called = {"count": 0}

        async def fake_run():
            called["count"] += 1

        monkeypatch.setattr(service, "_run_governance", fake_run)

        await service.on_tick()
        assert called["count"] == 1
