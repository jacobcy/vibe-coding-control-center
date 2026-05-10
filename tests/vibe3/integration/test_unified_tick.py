"""Integration tests for unified tick architecture.

Tests the complete scan/heartbeat pipeline:
  TickRequest → TickPlanner → TickPlan → TickDispatcher → internal commands

This validates:
1. Architecture: scan and heartbeat use unified chain
2. Commands: all scan variants work correctly
3. Integration: planner/dispatcher/internal work together
4. No regressions: internal commands unchanged
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.scan import app as scan_app
from vibe3.models.tick import TickPhase, TickPlan, TickRequest, TickSource
from vibe3.services.tick_dispatcher import TickDispatcher
from vibe3.services.tick_planner import TickPlanner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_orchestra_config() -> MagicMock:
    """Create mock orchestra configuration."""
    config = MagicMock()
    config.repo = "test/repo"
    config.governance = MagicMock()
    config.governance.materials = ["roadmap-intake", "roadmap-review"]
    return config


@pytest.fixture
def mock_governance_runner() -> MagicMock:
    """Mock run_governance_sync to avoid actual execution."""
    with patch(
        "vibe3.execution.governance_sync_runner.run_governance_sync"
    ) as mock_runner:
        yield mock_runner


@pytest.fixture
def mock_supervisor_runner() -> MagicMock:
    """Mock run_supervisor_apply to avoid actual execution."""
    with patch(
        "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
    ) as mock_runner:
        yield mock_runner


@pytest.fixture
def mock_scan_service() -> MagicMock:
    """Mock fetch_supervisor_candidates to avoid GitHub API calls."""
    with patch("vibe3.services.scan_service.fetch_supervisor_candidates") as mock:
        mock.return_value = [
            {"number": 743, "title": "Test issue 743"},
            {"number": 744, "title": "Test issue 744"},
        ]
        yield mock


class TestTickModels:
    """Test TickRequest and TickPlan models."""

    def test_tick_request_defaults(self) -> None:
        """TickRequest should have sensible defaults."""
        request = TickRequest(source=TickSource.MANUAL_SCAN)

        assert request.source == TickSource.MANUAL_SCAN
        assert request.tick_id == 0
        assert request.phases == [
            TickPhase.GOVERNANCE,
            TickPhase.SUPERVISOR,
        ]
        assert request.governance_material is None
        assert request.supervisor_issue_numbers == []
        assert request.dry_run is False

    def test_tick_request_frozen(self) -> None:
        """TickRequest should be immutable."""
        request = TickRequest(source=TickSource.MANUAL_SCAN)

        with pytest.raises(Exception):  # Pydantic ValidationError
            request.tick_id = 999

    def test_tick_plan_from_request_governance_only(
        self, mock_orchestra_config: MagicMock
    ) -> None:
        """TickPlan should resolve governance-only request."""
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.GOVERNANCE],
            governance_material="roadmap-intake",
        )

        plan = TickPlan.from_request(request, mock_orchestra_config, tick_count=0)

        assert plan.governance_enabled is True
        assert plan.governance_material == "roadmap-intake"
        assert plan.supervisor_enabled is False
        assert plan.supervisor_issues == []
        assert plan.dry_run is False

    def test_tick_plan_from_request_supervisor_only(
        self, mock_orchestra_config: MagicMock
    ) -> None:
        """TickPlan should resolve supervisor-only request."""
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.SUPERVISOR],
            supervisor_issue_numbers=[743],
        )

        plan = TickPlan.from_request(request, mock_orchestra_config, tick_count=0)

        assert plan.governance_enabled is False
        assert plan.governance_material is None
        assert plan.supervisor_enabled is True
        assert plan.supervisor_issues == [743]
        assert plan.dry_run is False

    def test_tick_plan_from_request_both_phases(
        self, mock_orchestra_config: MagicMock
    ) -> None:
        """TickPlan should resolve both phases."""
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.GOVERNANCE, TickPhase.SUPERVISOR],
            governance_material="roadmap-review",
            supervisor_issue_numbers=[743, 744],
        )

        plan = TickPlan.from_request(request, mock_orchestra_config, tick_count=0)

        assert plan.governance_enabled is True
        assert plan.governance_material == "roadmap-review"
        assert plan.supervisor_enabled is True
        assert plan.supervisor_issues == [743, 744]

    def test_tick_plan_from_request_auto_material(
        self, mock_orchestra_config: MagicMock
    ) -> None:
        """TickPlan should auto-select governance material when None."""
        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.GOVERNANCE],
            governance_material=None,  # Auto-select
        )

        # Mock _resolve_governance_material
        with patch(
            "vibe3.roles.governance._resolve_governance_material",
            return_value="roadmap-intake",
        ) as mock_resolve:
            plan = TickPlan.from_request(request, mock_orchestra_config, tick_count=0)

            # Should call resolver with tick_count=0
            mock_resolve.assert_called_once_with(mock_orchestra_config, 0)
            assert plan.governance_material == "roadmap-intake"


class TestTickPlanner:
    """Test TickPlanner service."""

    def test_planner_creates_plan(self, mock_orchestra_config: MagicMock) -> None:
        """TickPlanner.plan should create TickPlan from TickRequest."""
        planner = TickPlanner(mock_orchestra_config)

        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.GOVERNANCE],
            governance_material="test-material",
        )

        plan = planner.plan(request, tick_count=0)

        assert isinstance(plan, TickPlan)
        assert plan.governance_enabled is True
        assert plan.governance_material == "test-material"

    def test_planner_with_none_config(self) -> None:
        """TickPlanner should handle None config gracefully."""
        planner = TickPlanner(None)

        request = TickRequest(
            source=TickSource.MANUAL_SCAN,
            phases=[TickPhase.GOVERNANCE],
        )

        plan = planner.plan(request, tick_count=0)

        # Should still create plan, but governance_material will be None
        assert plan.governance_enabled is True
        assert plan.governance_material is None


class TestTickDispatcher:
    """Test TickDispatcher service."""

    def test_dispatcher_dry_run_prints_plan(
        self, mock_orchestra_config: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """TickDispatcher should print plan in dry-run mode."""
        dispatcher = TickDispatcher(mock_orchestra_config)

        plan = TickPlan(
            governance_enabled=True,
            governance_material="roadmap-intake",
            supervisor_enabled=True,
            supervisor_issues=[743],
            dry_run=True,
        )

        dispatcher.dispatch(plan)

        # Check dry-run output
        captured = capsys.readouterr()
        assert "Dry-Run: Tick Execution Plan" in captured.out
        assert "Governance:" in captured.out
        assert "roadmap-intake" in captured.out
        assert "Supervisor:" in captured.out
        assert "743" in captured.out

    def test_dispatcher_executes_governance(
        self,
        mock_orchestra_config: MagicMock,
        mock_governance_runner: MagicMock,
    ) -> None:
        """TickDispatcher should call run_governance_sync."""
        dispatcher = TickDispatcher(mock_orchestra_config)

        plan = TickPlan(
            governance_enabled=True,
            governance_material="roadmap-intake",
            supervisor_enabled=False,
            supervisor_issues=[],
            dry_run=False,
        )

        dispatcher.dispatch(plan)

        # Should call governance runner with correct params
        mock_governance_runner.assert_called_once_with(
            tick_count=0,
            material_override="roadmap-intake",
            dry_run=False,
            show_prompt=False,
            session_id=None,
        )

    def test_dispatcher_executes_supervisor_explicit(
        self,
        mock_orchestra_config: MagicMock,
        mock_supervisor_runner: MagicMock,
    ) -> None:
        """TickDispatcher should call run_supervisor_apply for explicit issues."""
        dispatcher = TickDispatcher(mock_orchestra_config)

        plan = TickPlan(
            governance_enabled=False,
            governance_material=None,
            supervisor_enabled=True,
            supervisor_issues=[743],
            dry_run=False,
        )

        dispatcher.dispatch(plan)

        # Should call supervisor runner with correct params
        mock_supervisor_runner.assert_called_once_with(
            issue_number=743,
            dry_run=False,
            fresh_session=True,
        )

    def test_dispatcher_scans_supervisor_candidates(
        self,
        mock_orchestra_config: MagicMock,
        mock_supervisor_runner: MagicMock,
        mock_scan_service: MagicMock,
    ) -> None:
        """TickDispatcher should scan for candidates when issues empty."""
        dispatcher = TickDispatcher(mock_orchestra_config)

        plan = TickPlan(
            governance_enabled=False,
            governance_material=None,
            supervisor_enabled=True,
            supervisor_issues=[],  # Empty = scan
            dry_run=False,
        )

        dispatcher.dispatch(plan)

        # Should scan for candidates
        mock_scan_service.assert_called_once()

        # Should call supervisor runner for each candidate
        assert mock_supervisor_runner.call_count == 2
        calls = mock_supervisor_runner.call_args_list
        assert calls[0][1]["issue_number"] == 743
        assert calls[1][1]["issue_number"] == 744

    def test_dispatcher_executes_both_phases(
        self,
        mock_orchestra_config: MagicMock,
        mock_governance_runner: MagicMock,
        mock_supervisor_runner: MagicMock,
    ) -> None:
        """TickDispatcher should execute both phases in order."""
        dispatcher = TickDispatcher(mock_orchestra_config)

        plan = TickPlan(
            governance_enabled=True,
            governance_material="roadmap-intake",
            supervisor_enabled=True,
            supervisor_issues=[743],
            dry_run=False,
        )

        dispatcher.dispatch(plan)

        # Both runners should be called
        mock_governance_runner.assert_called_once()
        mock_supervisor_runner.assert_called_once()


class TestScanCommandIntegration:
    """Integration tests for scan command with unified architecture."""

    def test_scan_governance_dry_run_displays_material(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
    ) -> None:
        """scan --governance --dry-run should display material."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(
                scan_app,
                [
                    "--governance",
                    "--governance-material",
                    "roadmap-intake",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            assert "Dry-Run: Tick Execution Plan" in result.output
            assert "Governance:" in result.output
            assert "roadmap-intake" in result.output
            assert "Supervisor:" not in result.output  # Not enabled

    def test_scan_supervisor_dry_run_displays_issues(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
    ) -> None:
        """scan --supervisor --dry-run should display issue list."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(
                scan_app, ["--supervisor", "--supervisor-issue", "743", "--dry-run"]
            )

            assert result.exit_code == 0
            assert "Dry-Run: Tick Execution Plan" in result.output
            assert "Governance:" not in result.output  # Not enabled
            assert "Supervisor:" in result.output
            assert "743" in result.output

    def test_scan_combined_dry_run(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
    ) -> None:
        """scan -g -gm -s -si --dry-run should show both phases."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(
                scan_app,
                [
                    "--governance",
                    "--governance-material",
                    "roadmap-review",
                    "--supervisor",
                    "--supervisor-issue",
                    "743",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            assert "Dry-Run: Tick Execution Plan" in result.output
            assert "Governance:" in result.output
            assert "roadmap-review" in result.output
            assert "Supervisor:" in result.output
            assert "743" in result.output

    def test_scan_default_runs_both_phases(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
        mock_governance_runner: MagicMock,
        mock_supervisor_runner: MagicMock,
        mock_scan_service: MagicMock,
    ) -> None:
        """scan (no flags) should run both phases."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(scan_app, [])

            assert result.exit_code == 0
            mock_governance_runner.assert_called_once()
            # Should scan for supervisor candidates
            mock_scan_service.assert_called_once()

    def test_scan_governance_only(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
        mock_governance_runner: MagicMock,
        mock_supervisor_runner: MagicMock,
    ) -> None:
        """scan --governance should only run governance phase."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(scan_app, ["--governance"])

            assert result.exit_code == 0
            mock_governance_runner.assert_called_once()
            mock_supervisor_runner.assert_not_called()

    def test_scan_supervisor_only(
        self,
        cli_runner: CliRunner,
        mock_orchestra_config: MagicMock,
        mock_governance_runner: MagicMock,
        mock_supervisor_runner: MagicMock,
        mock_scan_service: MagicMock,
    ) -> None:
        """scan --supervisor should only run supervisor phase."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(scan_app, ["--supervisor"])

            assert result.exit_code == 0
            mock_governance_runner.assert_not_called()
            mock_scan_service.assert_called_once()

    def test_scan_governance_material_requires_governance(
        self, cli_runner: CliRunner, mock_orchestra_config: MagicMock
    ) -> None:
        """--governance-material requires --governance."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(
                scan_app, ["--governance-material", "roadmap-intake"]
            )

            assert result.exit_code == 1
            assert "--governance-material requires --governance" in result.output

    def test_scan_supervisor_issue_requires_supervisor(
        self, cli_runner: CliRunner, mock_orchestra_config: MagicMock
    ) -> None:
        """--supervisor-issue requires --supervisor."""
        with patch(
            "vibe3.commands.scan.load_orchestra_config",
            return_value=mock_orchestra_config,
        ):
            result = cli_runner.invoke(scan_app, ["--supervisor-issue", "743"])

            assert result.exit_code == 1
            assert "--supervisor-issue requires --supervisor" in result.output


class TestInternalGovernanceStillWorks:
    """Regression tests: internal governance command unchanged."""

    def test_internal_governance_runner_signature(self) -> None:
        """run_governance_sync should have stable signature."""
        # Import real function, not mock
        # Check signature exists and has expected parameters
        import inspect

        from vibe3.execution.governance_sync_runner import run_governance_sync

        sig = inspect.signature(run_governance_sync)
        params = list(sig.parameters.keys())

        assert "tick_count" in params
        assert "material_override" in params
        assert "dry_run" in params
        assert "show_prompt" in params
        assert "session_id" in params


class TestInternalSupervisorStillWorks:
    """Regression tests: internal supervisor command unchanged."""

    def test_internal_supervisor_runner_signature(self) -> None:
        """run_supervisor_apply should have stable signature."""
        # Import real function, not mock
        # Check signature exists and has expected parameters
        import inspect

        from vibe3.execution.supervisor_apply_runner import run_supervisor_apply

        sig = inspect.signature(run_supervisor_apply)
        params = list(sig.parameters.keys())

        assert "issue_number" in params
        assert "dry_run" in params
        assert "fresh_session" in params


class TestArchitectureValidation:
    """Validate architecture invariants."""

    def test_scan_uses_tick_planner(self) -> None:
        """scan command should import TickPlanner."""
        import vibe3.commands.scan as scan_module

        # Check TickPlanner is imported
        assert hasattr(scan_module, "TickPlanner")

        # Check it's used in implementation
        import inspect

        source = inspect.getsource(scan_module.scan)
        assert "TickPlanner" in source
        assert "planner.plan" in source

    def test_scan_uses_tick_dispatcher(self) -> None:
        """scan command should import TickDispatcher."""
        import vibe3.commands.scan as scan_module

        # Check TickDispatcher is imported
        assert hasattr(scan_module, "TickDispatcher")

        # Check it's used in implementation
        import inspect

        source = inspect.getsource(scan_module.scan)
        assert "TickDispatcher" in source
        assert "dispatcher.dispatch" in source

    def test_dispatcher_uses_internal_governance(self) -> None:
        """TickDispatcher should call internal governance runner."""
        import inspect

        import vibe3.services.tick_dispatcher as dispatcher_module

        source = inspect.getsource(
            dispatcher_module.TickDispatcher._dispatch_governance
        )
        assert "run_governance_sync" in source

    def test_dispatcher_uses_internal_supervisor(self) -> None:
        """TickDispatcher should call internal supervisor runner."""
        import inspect

        import vibe3.services.tick_dispatcher as dispatcher_module

        source = inspect.getsource(
            dispatcher_module.TickDispatcher._dispatch_supervisor
        )
        assert "run_supervisor_apply" in source

    def test_planner_does_not_execute(self) -> None:
        """TickPlanner should not execute anything."""
        import inspect

        import vibe3.services.tick_planner as planner_module

        source = inspect.getsource(planner_module.TickPlanner)

        # Should not import or call execution modules
        assert "run_governance" not in source
        assert "run_supervisor" not in source
        # Note: "dispatch" appears in docstrings, so check method calls
        assert "dispatcher.dispatch" not in source
        assert ".dispatch(" not in source

    def test_models_frozen(self) -> None:
        """TickRequest and TickPlan should be immutable."""
        from vibe3.models.tick import TickPlan, TickRequest

        # Check model_config has frozen=True
        assert TickRequest.model_config.get("frozen") is True
        assert TickPlan.model_config.get("frozen") is True
