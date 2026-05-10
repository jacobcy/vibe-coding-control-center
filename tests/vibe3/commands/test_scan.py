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
        assert "--dry-run" in output


class TestGovernanceScan:
    """Tests for scan governance subcommand."""

    def test_governance_dry_run(self):
        """Test governance scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "governance", "--dry-run"])
        assert result.exit_code == 0
        # Should now show material information and prompt preview
        output_lower = result.output.lower()
        assert "material:" in output_lower or "governance scan dry-run" in output_lower

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_execution(self, mock_run):
        """Test governance scan execution."""
        result = runner.invoke(app, ["scan", "governance"])
        assert result.exit_code == 0
        assert "Governance scan completed" in result.output
        mock_run.assert_called_once_with(material_override=None)


class TestSupervisorScan:
    """Tests for scan supervisor subcommand."""

    def test_supervisor_dry_run(self):
        """Test supervisor scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        # Should show scan information
        output_lower = result.output.lower()
        assert "supervisor" in output_lower
        assert "dry-run" in output_lower or "dry run" in output_lower

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

    @patch("vibe3.commands.scan._run_combined_scan_async")
    def test_all_execution(self, mock_run):
        """Test combined scan execution."""
        mock_run.return_value = None
        result = runner.invoke(app, ["scan", "all"])
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

            _run_governance_scan()

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
                return (10, 2)

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

            _run_governance_scan()

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

            await _run_combined_scan_async()

            # Verify FailedGate was checked
            mock_gate_instance.check.assert_called_once()

            # Verify neither facade method was called (blocked by gate)
            mock_facade_instance.on_heartbeat_tick.assert_not_called()
            mock_facade_instance.on_supervisor_scan.assert_not_called()


# Tests for material description extraction
def test_extract_material_description_from_assignee_pool():
    """Test extracting description from assignee-pool.md."""
    from vibe3.commands.scan import _extract_material_description

    description = _extract_material_description(
        "supervisor/governance/assignee-pool.md"
    )
    assert description == "Assignee Pool 治理材料"


def test_extract_material_description_from_roadmap_intake():
    """Test extracting description from roadmap-intake.md."""
    from vibe3.commands.scan import _extract_material_description

    description = _extract_material_description(
        "supervisor/governance/roadmap-intake.md"
    )
    assert description == "Roadmap Intake 治理材料"


def test_extract_material_description_handles_missing_file():
    """Test handling missing file gracefully."""
    from vibe3.commands.scan import _extract_material_description

    description = _extract_material_description("supervisor/governance/nonexistent.md")
    assert description == "supervisor/governance/nonexistent.md"


def test_extract_material_description_handles_no_title():
    """Test handling file without title."""
    import tempfile
    from pathlib import Path

    from vibe3.commands.scan import _extract_material_description

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Some content without title\n")
        temp_path = f.name

    try:
        description = _extract_material_description(temp_path)
        # Should fall back to filename when no title
        assert description == temp_path
    finally:
        Path(temp_path).unlink()


# Tests for --list parameter
def test_governance_list_shows_materials():
    """Test that --list shows governance materials."""
    result = runner.invoke(app, ["scan", "governance", "--list"])

    assert result.exit_code == 0
    assert "Available Governance Materials" in result.stdout
    # Should show at least assignee-pool
    assert "assignee-pool" in result.stdout or "Assignee Pool" in result.stdout


def test_governance_list_mutually_exclusive_with_role():
    """Test that --list and --role are mutually exclusive."""
    result = runner.invoke(
        app, ["scan", "governance", "--list", "--role", "assignee-pool"]
    )

    # Should error with clear message
    assert result.exit_code != 0
    assert "cannot be used together" in result.output.lower()


class TestGovernanceDryRunPromptDisplay:
    """Tests for governance --dry-run prompt display."""

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_dry_run_shows_material_info(self, mock_run):
        """Test that --dry-run shows which material would be used."""
        result = runner.invoke(
            app, ["scan", "governance", "--role", "assignee-pool", "--dry-run"]
        )

        assert result.exit_code == 0
        # Should show material information
        assert "assignee-pool" in result.output.lower() or "Material:" in result.output

    def test_governance_dry_run_shows_prompt_preview(self):
        """Test that --dry-run displays rendered prompt."""
        result = runner.invoke(
            app, ["scan", "governance", "--role", "assignee-pool", "--dry-run"]
        )

        assert result.exit_code == 0
        # Should show prompt preview section
        output_lower = result.output.lower()
        assert "prompt" in output_lower or "governance prompt" in output_lower


class TestSupervisorDryRunPromptDisplay:
    """Tests for supervisor --dry-run prompt display."""

    def test_supervisor_dry_run_shows_scan_info(self):
        """Test that --dry-run shows scan information."""
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])

        assert result.exit_code == 0
        # Should show scan information
        output_lower = result.output.lower()
        assert "supervisor" in output_lower
        assert "dry-run" in output_lower or "dry run" in output_lower

    @patch("vibe3.commands.scan._run_supervisor_scan_dry_run")
    def test_supervisor_dry_run_calls_handler(self, mock_run):
        """Test that --dry-run calls the dry-run handler."""
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])

        assert result.exit_code == 0
        mock_run.assert_called_once()


class TestCombinedScanDryRun:
    """Tests for scan all --dry-run functionality."""

    @patch("vibe3.commands.scan._run_governance_scan_dry_run")
    @patch("vibe3.commands.scan._run_supervisor_scan_dry_run")
    def test_all_dry_run_calls_both_handlers(self, mock_supervisor, mock_governance):
        """Test that 'scan all --dry-run' calls both dry-run handlers."""
        result = runner.invoke(app, ["scan", "all", "--dry-run"])

        assert result.exit_code == 0
        mock_governance.assert_called_once()
        mock_supervisor.assert_called_once()
