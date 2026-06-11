"""Tests for scan CLI command."""

import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestScanCommand:
    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Run governance and supervisor scans" in result.output
        assert "governance" in result.output
        assert "supervisor" in result.output
        assert "all" in result.output

    def test_scan_governance_help(self):
        result = runner.invoke(app, ["scan", "governance", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run governance scan once" in output
        assert "--dry-run" in output
        assert "--no-async" in output

    def test_scan_supervisor_help(self):
        result = runner.invoke(app, ["scan", "supervisor", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run supervisor scan once" in output
        assert "--dry-run" in output

    def test_scan_all_help(self):
        result = runner.invoke(app, ["scan", "all", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Run both governance and supervisor scans once" in output
        assert "--dry-run" in output


class TestGovernanceScan:
    @pytest.mark.slow
    def test_governance_dry_run(self):
        result = runner.invoke(app, ["scan", "governance", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "governance dry-run" in output_lower or "--- prompt ---" in output_lower

    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_execution(self, mock_run):
        result = runner.invoke(app, ["scan", "governance", "--no-async"])
        assert result.exit_code == 0
        assert "Governance scan completed" in result.output
        mock_run.assert_called_once_with(material_override=None, no_async=True)

    def test_governance_scan_does_not_call_on_heartbeat_tick(self):
        """Sync path (--no-async) calls service layer directly, not through facade."""
        with patch("vibe3.roles.dispatch_governance_execution") as mock_service_run:
            with patch(
                "vibe3.domain.orchestration_facade.OrchestrationFacade"
            ) as mock_facade:
                runner.invoke(app, ["scan", "governance", "--no-async"])
                mock_facade.assert_not_called()
                assert mock_service_run.called
                mock_service_run.assert_called_once_with(material_override=None)


class TestSupervisorScan:
    def test_supervisor_dry_run(self):
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "supervisor" in output_lower
        assert "dry-run" in output_lower or "dry run" in output_lower

    @patch("vibe3.commands.scan._run_supervisor_scan")
    def test_supervisor_execution(self, mock_run):
        mock_run.return_value = (10, 2)
        result = runner.invoke(app, ["scan", "supervisor"])
        assert result.exit_code == 0
        assert "Scanned 10 open issues" in result.output
        assert "found 2" in result.output


class TestCombinedScan:
    @pytest.mark.slow
    def test_all_dry_run(self):
        result = runner.invoke(app, ["scan", "all", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "governance dry-run" in output_lower
        assert "supervisor scan dry-run" in output_lower

    @patch("vibe3.commands.scan._run_combined_scan_async")
    def test_all_execution(self, mock_run):
        mock_run.return_value = None
        result = runner.invoke(app, ["scan", "all"])
        assert result.exit_code == 0
        assert "Combined scan completed" in result.output


class TestScanIntegration:
    def test_governance_scan_registers_handlers(self):
        """Sync governance scan calls service layer directly, not facade."""
        with patch("vibe3.roles.dispatch_governance_execution") as mock_service:
            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan(no_async=True)
            mock_service.assert_called_once_with(material_override=None)

    def test_supervisor_scan_registers_handlers(self):
        """Supervisor scan calls service layer directly, not facade."""
        with (
            patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
            patch("vibe3.roles.dispatch_supervisor_execution") as mock_apply,
        ):
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
            mock_fetch.assert_called_once()
            mock_apply.assert_called_once()


class TestFailedGateBlocking:
    def test_governance_scan_blocked_by_failed_gate(self):
        """Sync governance scan ignores FailedGate (only for heartbeat)."""
        with patch("vibe3.roles.dispatch_governance_execution") as mock_service:
            from vibe3.commands.scan import _run_governance_scan

            _run_governance_scan(no_async=True)
            mock_service.assert_called_once_with(material_override=None)

    def test_supervisor_scan_blocked_by_failed_gate(self):
        """Manual supervisor scan ignores FailedGate (only for heartbeat)."""
        with patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch:
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_supervisor_scan

            _run_supervisor_scan()
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_combined_scan_blocked_by_failed_gate(self):
        """Combined scan bypasses FailedGate for both governance and supervisor."""
        with (
            patch("vibe3.roles.dispatch_governance_execution") as mock_governance,
            patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
            patch("vibe3.roles.dispatch_supervisor_execution"),
        ):
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_combined_scan_async

            await _run_combined_scan_async()
            mock_governance.assert_called_once()
            mock_fetch.assert_called_once()


def test_supervisor_scan_fetches_candidates_and_calls_service_apply() -> None:
    """Manual supervisor scan fetches candidates and dispatches each."""
    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.roles.dispatch_supervisor_execution") as mock_apply,
    ):
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
        mock_fetch.assert_called_once()
        assert mock_apply.call_count == 2


def test_governance_list_shows_materials():
    result = runner.invoke(app, ["scan", "governance", "--list"])
    assert result.exit_code == 0
    assert "Available Governance Materials" in result.stdout
    assert "assignee-pool" in result.stdout or "Assignee Pool" in result.stdout


def test_governance_list_mutually_exclusive_with_role():
    result = runner.invoke(
        app, ["scan", "governance", "--list", "--role", "assignee-pool"]
    )
    assert result.exit_code != 0
    assert "cannot be used together" in result.output.lower()


def test_governance_invalid_role_shows_friendly_error():
    result = runner.invoke(app, ["scan", "governance", "--role", "does-not-exist"])
    assert result.exit_code != 0
    output = _strip_ansi(result.output)
    assert "does-not-exist" in output
    assert "available roles" in output.lower()
    assert "traceback" not in output.lower()


@pytest.mark.slow
class TestGovernanceDryRunPromptDisplay:
    @patch("vibe3.commands.scan._run_governance_scan")
    def test_governance_dry_run_shows_material_info(self, mock_run):
        result = runner.invoke(
            app, ["scan", "governance", "--role", "assignee-pool", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "assignee-pool" in result.output.lower() or "Material:" in result.output

    @pytest.mark.slow
    def test_governance_dry_run_shows_prompt_preview(self):
        result = runner.invoke(
            app, ["scan", "governance", "--role", "assignee-pool", "--dry-run"]
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "prompt" in output_lower or "governance prompt" in output_lower


class TestSupervisorDryRunPromptDisplay:
    @pytest.mark.slow
    def test_supervisor_dry_run_shows_scan_info(self):
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "supervisor" in output_lower
        assert "dry-run" in output_lower or "dry run" in output_lower

    @patch("vibe3.commands.scan._run_supervisor_scan_dry_run")
    def test_supervisor_dry_run_calls_handler(self, mock_run):
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


class TestCombinedScanDryRun:
    @patch("vibe3.commands.scan._run_governance_scan_dry_run")
    @patch("vibe3.commands.scan._run_supervisor_scan_dry_run")
    def test_all_dry_run_calls_both_handlers(self, mock_supervisor, mock_governance):
        result = runner.invoke(app, ["scan", "all", "--dry-run"])
        assert result.exit_code == 0
        mock_governance.assert_called_once()
        mock_supervisor.assert_called_once()
