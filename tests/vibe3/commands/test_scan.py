"""Tests for scan CLI command."""

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestScanCommand:
    """Tests for scan CLI command group."""

    def test_scan_help(self):
        """Test scan command shows help."""
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Run governance and supervisor scans" in result.output
        assert "governance" in result.output
        assert "supervisor" in result.output
        assert "all" in result.output

    def test_scan_governance_help(self):
        """Test scan governance subcommand help."""
        result = runner.invoke(app, ["scan", "governance", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run governance scan once" in output
        assert "--tick" in output
        assert "--dry-run" in output

    def test_scan_supervisor_help(self):
        """Test scan supervisor subcommand help."""
        result = runner.invoke(app, ["scan", "supervisor", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run supervisor scan once" in output
        assert "--dry-run" in output

    def test_scan_all_help(self):
        """Test scan all subcommand help."""
        result = runner.invoke(app, ["scan", "all", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run both governance and supervisor scans once" in output
        assert "--tick" in output
        assert "--dry-run" in output


class TestGovernanceScan:
    """Tests for scan governance subcommand."""

    def test_governance_dry_run(self):
        """Test governance scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "governance", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN: Would run governance scan" in result.output

    def test_governance_dry_run_with_tick(self):
        """Test governance scan dry-run with custom tick count."""
        result = runner.invoke(app, ["scan", "governance", "--dry-run", "--tick", "42"])
        assert result.exit_code == 0
        assert "DRY RUN: Would run governance scan" in result.output
        assert "Using tick count: 42" in result.output

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_execution(self, mock_run):
        """Test governance scan execution."""
        result = runner.invoke(app, ["scan", "governance"])
        assert result.exit_code == 0
        assert "Governance scan completed" in result.output
        mock_run.assert_called_once_with(tick_count=None)

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_execution_with_tick(self, mock_run):
        """Test governance scan execution with custom tick."""
        result = runner.invoke(app, ["scan", "governance", "--tick", "100"])
        assert result.exit_code == 0
        assert "Governance scan completed" in result.output
        mock_run.assert_called_once_with(tick_count=100)


class TestSupervisorScan:
    """Tests for scan supervisor subcommand."""

    def test_supervisor_dry_run(self):
        """Test supervisor scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN: Would run supervisor scan" in result.output

    @patch("vibe3.commands.scan._run_supervisor_scan_async")
    def test_supervisor_execution(self, mock_run):
        """Test supervisor scan execution."""
        # Mock async function needs to return a coroutine
        mock_run.return_value = None
        result = runner.invoke(app, ["scan", "supervisor"])
        assert result.exit_code == 0
        assert "Supervisor scan completed" in result.output


class TestCombinedScan:
    """Tests for scan all subcommand."""

    def test_all_dry_run(self):
        """Test combined scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "all", "--dry-run"])
        assert result.exit_code == 0
        assert (
            "DRY RUN: Would run both governance and supervisor scans" in result.output
        )

    def test_all_dry_run_with_tick(self):
        """Test combined scan dry-run with custom tick count."""
        result = runner.invoke(app, ["scan", "all", "--dry-run", "--tick", "50"])
        assert result.exit_code == 0
        assert (
            "DRY RUN: Would run both governance and supervisor scans" in result.output
        )
        assert "Using tick count: 50" in result.output

    @patch("vibe3.commands.scan._run_combined_scan_async")
    def test_all_execution(self, mock_run):
        """Test combined scan execution."""
        mock_run.return_value = None
        result = runner.invoke(app, ["scan", "all"])
        assert result.exit_code == 0
        assert "Combined scan completed" in result.output

    @patch("vibe3.commands.scan._run_combined_scan_async")
    def test_all_execution_with_tick(self, mock_run):
        """Test combined scan execution with custom tick."""
        mock_run.return_value = None
        result = runner.invoke(app, ["scan", "all", "--tick", "75"])
        assert result.exit_code == 0
        assert "Combined scan completed" in result.output


class TestScanIntegration:
    """Integration tests for scan command with services."""

    def test_governance_scan_registers_handlers(self):
        """Test that governance scan registers event handlers."""
        with (
            patch("vibe3.domain.handlers.register_event_handlers") as mock_handlers,
            patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade,
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.orchestra.failed_gate.FailedGate") as mock_failed_gate,
            patch("vibe3.execution.capacity_service.CapacityService"),
            patch("vibe3.config.orchestra_settings.load_orchestra_config"),
        ):

            # Mock FailedGate to return open gate
            mock_gate_instance = MagicMock()
            mock_gate_result = MagicMock()
            mock_gate_result.blocked = False
            mock_gate_instance.check.return_value = mock_gate_result
            mock_failed_gate.return_value = mock_gate_instance

            mock_facade_instance = MagicMock()
            mock_facade.return_value = mock_facade_instance

            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan(tick_count=10)

            # Verify handlers were registered before facade methods called
            mock_handlers.assert_called_once()
            mock_facade.assert_called_once()
            mock_facade_instance.on_heartbeat_tick.assert_called_once()

    @pytest.mark.asyncio
    async def test_supervisor_scan_registers_handlers(self):
        """Test that supervisor scan registers event handlers."""
        with (
            patch("vibe3.domain.handlers.register_event_handlers") as mock_handlers,
            patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade,
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.orchestra.failed_gate.FailedGate") as mock_failed_gate,
            patch("vibe3.execution.capacity_service.CapacityService"),
            patch("vibe3.config.orchestra_settings.load_orchestra_config"),
        ):

            # Mock FailedGate to return open gate
            mock_gate_instance = MagicMock()
            mock_gate_result = MagicMock()
            mock_gate_result.blocked = False
            mock_gate_instance.check.return_value = mock_gate_result
            mock_failed_gate.return_value = mock_gate_instance

            mock_facade_instance = MagicMock()

            # Make on_supervisor_scan an async mock
            async def async_mock():
                pass

            mock_facade_instance.on_supervisor_scan = async_mock
            mock_facade.return_value = mock_facade_instance

            from vibe3.commands.scan import _run_supervisor_scan_async

            await _run_supervisor_scan_async()

            # Verify handlers were registered
            mock_handlers.assert_called_once()
            mock_facade.assert_called_once()


class TestFailedGateBlocking:
    """Tests for FailedGate blocking in scan commands."""

    def test_governance_scan_blocked_by_failed_gate(self):
        """Test that governance scan respects FailedGate."""
        with (
            patch("vibe3.domain.handlers.register_event_handlers"),
            patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade,
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.orchestra.failed_gate.FailedGate") as mock_failed_gate,
            patch("vibe3.execution.capacity_service.CapacityService"),
            patch("vibe3.config.orchestra_settings.load_orchestra_config"),
        ):

            # Mock FailedGate to return blocked state
            mock_gate_instance = MagicMock()
            mock_gate_result = MagicMock()
            mock_gate_result.blocked = True
            mock_gate_result.reason = "API error threshold: 2 recent errors"
            mock_gate_instance.check.return_value = mock_gate_result
            mock_failed_gate.return_value = mock_gate_instance

            mock_facade_instance = MagicMock()
            mock_facade.return_value = mock_facade_instance

            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan(tick_count=10)

            # Verify FailedGate was checked
            mock_gate_instance.check.assert_called_once()

            # Verify facade was NOT called (blocked by gate)
            mock_facade_instance.on_heartbeat_tick.assert_not_called()

    @pytest.mark.asyncio
    async def test_supervisor_scan_blocked_by_failed_gate(self):
        """Test that supervisor scan respects FailedGate."""
        with (
            patch("vibe3.domain.handlers.register_event_handlers"),
            patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade,
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.orchestra.failed_gate.FailedGate") as mock_failed_gate,
            patch("vibe3.execution.capacity_service.CapacityService"),
            patch("vibe3.config.orchestra_settings.load_orchestra_config"),
        ):

            # Mock FailedGate to return blocked state
            mock_gate_instance = MagicMock()
            mock_gate_result = MagicMock()
            mock_gate_result.blocked = True
            mock_gate_result.reason = "Model configuration errors: E_MODEL_INVALID"
            mock_gate_instance.check.return_value = mock_gate_result
            mock_failed_gate.return_value = mock_gate_instance

            mock_facade_instance = MagicMock()
            mock_facade_instance.on_supervisor_scan = MagicMock(return_value=None)
            mock_facade.return_value = mock_facade_instance

            from vibe3.commands.scan import _run_supervisor_scan_async

            await _run_supervisor_scan_async()

            # Verify FailedGate was checked
            mock_gate_instance.check.assert_called_once()

            # Verify facade was NOT called (blocked by gate)
            mock_facade_instance.on_supervisor_scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_combined_scan_blocked_by_failed_gate(self):
        """Test that combined scan respects FailedGate."""
        with (
            patch("vibe3.domain.handlers.register_event_handlers"),
            patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade,
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.orchestra.failed_gate.FailedGate") as mock_failed_gate,
            patch("vibe3.execution.capacity_service.CapacityService"),
            patch("vibe3.config.orchestra_settings.load_orchestra_config"),
        ):

            # Mock FailedGate to return blocked state
            mock_gate_instance = MagicMock()
            mock_gate_result = MagicMock()
            mock_gate_result.blocked = True
            mock_gate_result.reason = "System in failed state"
            mock_gate_instance.check.return_value = mock_gate_result
            mock_failed_gate.return_value = mock_gate_instance

            mock_facade_instance = MagicMock()
            mock_facade_instance.on_supervisor_scan = MagicMock(return_value=None)
            mock_facade.return_value = mock_facade_instance

            from vibe3.commands.scan import _run_combined_scan_async

            await _run_combined_scan_async(tick_count=20)

            # Verify FailedGate was checked
            mock_gate_instance.check.assert_called_once()

            # Verify neither facade method was called (blocked by gate)
            mock_facade_instance.on_heartbeat_tick.assert_not_called()
            mock_facade_instance.on_supervisor_scan.assert_not_called()
