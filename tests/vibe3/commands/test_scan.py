"""Tests for scan CLI command."""

import re
from unittest.mock import patch

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
        # New format: "-> Governance dry-run: tick=0"
        # Uses real-time snapshot via run_governance_sync(dry_run=True)
        output_lower = result.output.lower()
        assert "governance dry-run" in output_lower or "--- prompt ---" in output_lower

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_execution(self, mock_run):
        """Test governance scan execution."""
        result = runner.invoke(app, ["scan", "governance"])
        assert result.exit_code == 0
        assert "Governance scan completed" in result.output
        mock_run.assert_called_once_with(material_override=None)

    def test_governance_scan_does_not_call_on_heartbeat_tick(self):
        """Test manual governance scan does not call facade.on_heartbeat_tick.

        Manual scan should call internal_governance_dispatch directly,
        not through OrchestrationFacade heartbeat path.
        """
        # Mock the internal dispatch function that should be called
        with patch(
            "vibe3.commands.internal.internal_governance_dispatch"
        ) as mock_internal_dispatch:
            # Mock facade to ensure it's not created
            # OrchestrationFacade is imported inside _run_governance_scan
            with patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade:
                runner.invoke(app, ["scan", "governance"])

                # After refactor, facade should not be instantiated
                mock_facade.assert_not_called()

                # And internal dispatch should be called instead
                # (This will pass once we refactor _run_governance_scan)
                # For now, we expect this to fail as implementation
                # still uses facade
                if mock_internal_dispatch.called:
                    # Success: new implementation calls internal dispatch
                    pass
                else:
                    # Failure: old implementation still uses facade
                    # We'll fix this in Step 3
                    raise AssertionError(
                        "Implementation still uses facade, "
                        "should call internal dispatch"
                    )


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

    @patch("vibe3.commands.scan._run_supervisor_scan")
    def test_supervisor_execution(self, mock_run):
        """Test supervisor scan execution."""
        # Mock return value (total_scanned, matched_count)
        mock_run.return_value = (10, 2)
        result = runner.invoke(app, ["scan", "supervisor"])
        assert result.exit_code == 0
        # Should show scan statistics, not "completed" message
        assert "Scanned 10 open issues" in result.output
        assert "found 2" in result.output


class TestCombinedScan:
    """Tests for scan all subcommand."""

    def test_all_dry_run(self):
        """Test combined scan with --dry-run flag."""
        result = runner.invoke(app, ["scan", "all", "--dry-run"])
        assert result.exit_code == 0
        # Should show both governance and supervisor dry-run output
        output_lower = result.output.lower()
        # New format: "Governance dry-run" and "Supervisor scan dry-run"
        assert "governance dry-run" in output_lower
        assert "supervisor scan dry-run" in output_lower

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
        """Test that governance scan calls internal dispatch directly.

        After refactor: manual governance scan no longer registers handlers
        or uses facade. It calls internal_governance_dispatch directly.
        """
        with patch(
            "vibe3.commands.internal.internal_governance_dispatch"
        ) as mock_internal:
            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan()

            # Verify internal dispatch was called (new architecture)
            mock_internal.assert_called_once_with(tick=0, material=None)

    def test_supervisor_scan_registers_handlers(self):
        """Test that supervisor scan calls internal dispatch directly.

        After refactor: manual supervisor scan no longer registers handlers
        or uses facade. It calls internal_apply_dispatch directly.
        """
        with (
            patch(
                "vibe3.services.scan_service.fetch_supervisor_candidates"
            ) as mock_fetch,
            patch("vibe3.commands.internal.internal_apply_dispatch") as mock_apply,
        ):
            # Mock candidate list (total_scanned, candidates)
            mock_fetch.return_value = (
                1,
                [
                    {
                        "number": 123,
                        "title": "Issue A",
                        "labels": ["supervisor", "state/handoff"],
                    },
                ],
            )

            from vibe3.commands.scan import _run_supervisor_scan

            _run_supervisor_scan()

            # Verify candidates fetched
            mock_fetch.assert_called_once()
            # Verify internal dispatch called
            mock_apply.assert_called_once()


class TestFailedGateBlocking:
    """Tests for FailedGate blocking in scan commands."""

    def test_governance_scan_blocked_by_failed_gate(self):
        """Test that manual governance scan ignores FailedGate.

        After refactor: manual governance scan calls internal dispatch directly,
        bypassing FailedGate (which is only for heartbeat automatic chain).
        FailedGate is only checked in automatic heartbeat polling, not manual scans.
        """
        with patch(
            "vibe3.commands.internal.internal_governance_dispatch"
        ) as mock_internal:
            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan()

            # Manual scan always calls internal dispatch, ignoring FailedGate
            mock_internal.assert_called_once_with(tick=0, material=None)

    def test_supervisor_scan_blocked_by_failed_gate(self):
        """Test manual supervisor scan ignores FailedGate.

        After refactor: manual supervisor scan calls internal dispatch directly,
        bypassing FailedGate (which is only for heartbeat automatic chain).
        FailedGate is only checked in automatic heartbeat polling, not manual scans.
        """
        with patch(
            "vibe3.services.scan_service.fetch_supervisor_candidates"
        ) as mock_fetch:
            # Mock empty candidate list (total_scanned, candidates)
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_supervisor_scan

            _run_supervisor_scan()

            # Manual scan always fetches candidates, ignoring FailedGate
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_combined_scan_blocked_by_failed_gate(self):
        """Test combined scan bypasses FailedGate for both governance and supervisor.

        After refactor: manual scans bypass FailedGate entirely.
        FailedGate is only checked in automatic heartbeat polling.
        Both governance and supervisor use internal dispatch directly.
        """
        with (
            patch(
                "vibe3.commands.internal.internal_governance_dispatch"
            ) as mock_governance,
            patch(
                "vibe3.services.scan_service.fetch_supervisor_candidates"
            ) as mock_fetch,
            patch("vibe3.commands.internal.internal_apply_dispatch"),
        ):
            # Mock supervisor candidates (total_scanned, candidates)
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_combined_scan_async

            await _run_combined_scan_async()

            # Governance always runs (bypasses FailedGate)
            mock_governance.assert_called_once()

            # Supervisor also runs (bypasses FailedGate)
            mock_fetch.assert_called_once()


# Tests for material description extraction
def test_supervisor_scan_fetches_candidates_and_calls_internal_apply() -> None:
    """Test manual supervisor scan calls internal apply directly.

    After refactor: manual supervisor scan should fetch candidates,
    filter them, and call internal_apply_dispatch for each one,
    not through facade event chain.
    """
    with (
        patch("vibe3.services.scan_service.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.commands.internal.internal_apply_dispatch") as mock_apply,
    ):
        # Mock candidate list (total_scanned, candidates)
        mock_fetch.return_value = (
            2,
            [
                {
                    "number": 123,
                    "title": "Issue A",
                    "labels": ["supervisor", "state/handoff"],
                },
                {
                    "number": 456,
                    "title": "Issue B",
                    "labels": ["supervisor", "state/handoff"],
                },
            ],
        )

        result = runner.invoke(app, ["scan", "supervisor"])

        assert result.exit_code == 0
        # Should fetch candidates
        mock_fetch.assert_called_once()

        # Should call internal_apply_dispatch for each candidate
        assert mock_apply.call_count == 2


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
