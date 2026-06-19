"""Tests for combined scan CLI paths."""

import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def test_scan_governance_list_includes_audit_observation():
    result = runner.invoke(app, ["scan", "governance", "--list"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "audit-observation" in output


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


class TestFailedGateBlocking:
    @pytest.mark.asyncio
    async def test_combined_scan_ignores_failed_gate(self):
        """Combined scan bypasses FailedGate (publishes events directly)."""
        with (
            patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
            patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        ):
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_combined_scan_async
            from vibe3.domain import GovernanceScanStarted
            from vibe3.models import ExecutionLaunchResult

            mock_publish_and_wait.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="governance-123",
            )

            await _run_combined_scan_async()
            assert mock_publish_and_wait.call_count >= 1
            governance_event = mock_publish_and_wait.call_args.args[0]
            assert isinstance(governance_event, GovernanceScanStarted)
            mock_fetch.assert_called_once()


class TestCombinedScanDryRun:
    @patch("vibe3.commands.scan._run_governance_scan_dry_run")
    @patch("vibe3.commands.scan._run_supervisor_scan_dry_run")
    def test_all_dry_run_calls_both_handlers(self, mock_supervisor, mock_governance):
        result = runner.invoke(app, ["scan", "all", "--dry-run"])
        assert result.exit_code == 0
        mock_governance.assert_called_once()
        mock_supervisor.assert_called_once()
