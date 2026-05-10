"""Tests for refactored scan command using unified architecture."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.scan import app
from vibe3.models.tick import TickPhase, TickSource


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestScanCommand:
    """Tests for unified scan command."""

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_default_calls_both_phases(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test that default (no flags) executes both phases."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_plan.governance_enabled = True
        mock_plan.supervisor_enabled = True
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, [])

        # Verify execution
        assert result.exit_code == 0

        # Verify request was created with both phases
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]  # First positional argument

        assert request.source == TickSource.MANUAL_SCAN
        assert request.tick_id == 0
        assert TickPhase.GOVERNANCE in request.phases
        assert TickPhase.SUPERVISOR in request.phases
        assert request.dry_run is False

        # Verify dispatcher was called
        mock_dispatcher.dispatch.assert_called_once_with(mock_plan)

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_governance_only(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test --governance flag without --governance-material (auto-select)."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_plan.governance_enabled = True
        mock_plan.supervisor_enabled = False
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["--governance"])

        # Verify execution
        assert result.exit_code == 0

        # Verify request
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert request.source == TickSource.MANUAL_SCAN
        assert request.phases == [TickPhase.GOVERNANCE]
        assert request.governance_material is None  # Auto-select
        assert TickPhase.SUPERVISOR not in request.phases

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_governance_with_material(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test --governance with --governance-material."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(
            app, ["--governance", "--governance-material", "roadmap-intake"]
        )

        # Verify execution
        assert result.exit_code == 0

        # Verify request
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert request.phases == [TickPhase.GOVERNANCE]
        assert request.governance_material == "roadmap-intake"

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_supervisor_with_issue(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test --supervisor with --supervisor-issue."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["--supervisor", "--supervisor-issue", "743"])

        # Verify execution
        assert result.exit_code == 0

        # Verify request
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert request.phases == [TickPhase.SUPERVISOR]
        assert request.supervisor_issue_numbers == [743]

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_both_flags(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test both --governance and --supervisor flags."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(
            app,
            [
                "--governance",
                "--governance-material",
                "roadmap-intake",
                "--supervisor",
                "--supervisor-issue",
                "743",
            ],
        )

        # Verify execution
        assert result.exit_code == 0

        # Verify request
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert TickPhase.GOVERNANCE in request.phases
        assert TickPhase.SUPERVISOR in request.phases
        assert request.governance_material == "roadmap-intake"
        assert request.supervisor_issue_numbers == [743]

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_dry_run(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test --dry-run flag."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_plan.dry_run = True
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["--dry-run"])

        # Verify execution
        assert result.exit_code == 0

        # Verify request has dry_run=True
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert request.dry_run is True

        # Verify plan was created with dry_run
        mock_dispatcher.dispatch.assert_called_once()

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_verbose_flag(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test -v verbosity flag."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["-v"])

        # Verify execution
        assert result.exit_code == 0

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_scan_supervisor_scan_candidates(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test --supervisor without --supervisor-issue scans candidates."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_plan.supervisor_enabled = True
        mock_plan.supervisor_issues = []  # Empty = scan
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["--supervisor"])

        # Verify execution
        assert result.exit_code == 0

        # Verify request
        call_args = mock_planner.plan.call_args
        assert call_args is not None
        request = call_args[0][0]

        assert request.phases == [TickPhase.SUPERVISOR]
        assert request.supervisor_issue_numbers == []  # Empty = scan

    def test_governance_material_requires_governance(self, runner: CliRunner) -> None:
        """Test that --governance-material requires --governance."""
        result = runner.invoke(app, ["--governance-material", "roadmap-intake"])

        # Should fail with error message
        assert result.exit_code == 1
        assert "requires --governance" in result.output

    def test_supervisor_issue_requires_supervisor(self, runner: CliRunner) -> None:
        """Test that --supervisor-issue requires --supervisor."""
        result = runner.invoke(app, ["--supervisor-issue", "743"])

        # Should fail with error message
        assert result.exit_code == 1
        assert "requires --supervisor" in result.output


class TestDeprecatedCommands:
    """Tests for deprecated subcommands."""

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_governance_deprecated(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test deprecated 'governance' subcommand."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["governance"])

        # Verify deprecation warning
        assert "deprecated" in result.output.lower()
        assert result.exit_code == 0

        # Verify it still works
        assert mock_dispatcher.dispatch.call_count >= 1

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_supervisor_deprecated(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test deprecated 'supervisor' subcommand."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["supervisor"])

        # Verify deprecation warning
        assert "deprecated" in result.output.lower()
        assert result.exit_code == 0

        # Verify it still works
        assert mock_dispatcher.dispatch.call_count >= 1

    @patch("vibe3.commands.scan.TickDispatcher")
    @patch("vibe3.commands.scan.TickPlanner")
    @patch("vibe3.commands.scan.load_orchestra_config")
    def test_all_deprecated(
        self,
        mock_load_config: MagicMock,
        mock_planner_cls: MagicMock,
        mock_dispatcher_cls: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test deprecated 'all' subcommand."""
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_planner = MagicMock()
        mock_plan = MagicMock()
        mock_planner.plan.return_value = mock_plan
        mock_planner_cls.return_value = mock_planner

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        # Run command
        result = runner.invoke(app, ["all"])

        # Verify deprecation warning
        assert "deprecated" in result.output.lower()
        assert result.exit_code == 0

        # Verify it still works
        assert mock_dispatcher.dispatch.call_count >= 1
