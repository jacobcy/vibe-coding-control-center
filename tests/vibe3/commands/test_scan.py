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
        mock_run.assert_called_once_with(material_override=None, no_async=True)

    def test_governance_scan_publishes_event(self):
        """Governance scan publishes GovernanceScanStarted event."""
        with patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait:
            from vibe3.commands.scan import _run_governance_scan
            from vibe3.domain import GovernanceScanStarted
            from vibe3.models import ExecutionLaunchResult

            mock_publish_and_wait.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="governance-123",
                log_path="/tmp/events.log",
            )

            _run_governance_scan(no_async=True)
            mock_publish_and_wait.assert_called_once()
            event = mock_publish_and_wait.call_args.args[0]
            assert isinstance(event, GovernanceScanStarted)
            assert event.actor == "cli:scan-governance"
            assert event.tick_count == 0


class TestSupervisorScan:
    def test_supervisor_dry_run(self):
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "supervisor" in output_lower
        assert "dry-run" in output_lower or "dry run" in output_lower

    @patch("vibe3.commands.scan._run_supervisor_scan")
    def test_supervisor_execution(self, mock_run):
        # Mock returns values but function now handles display internally
        mock_run.return_value = (10, 2)
        result = runner.invoke(app, ["scan", "supervisor"])
        assert result.exit_code == 0
        # Function is mocked, so no output expected
        # The actual display happens in _run_supervisor_scan now


class TestScanIntegration:
    def test_governance_scan_registers_handlers(self):
        """Governance scan publishes event, not direct dispatch."""
        with patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait:
            from vibe3.commands.scan import _run_governance_scan
            from vibe3.domain import GovernanceScanStarted
            from vibe3.models import ExecutionLaunchResult

            mock_publish_and_wait.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="governance-123",
            )

            _run_governance_scan(no_async=True)
            mock_publish_and_wait.assert_called_once()
            event = mock_publish_and_wait.call_args.args[0]
            assert isinstance(event, GovernanceScanStarted)

    def test_supervisor_scan_publishes_events(self):
        """Supervisor scan publishes SupervisorIssueIdentified events."""
        with (
            patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
            patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
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
            # Mock returns a result
            from vibe3.models import ExecutionLaunchResult

            mock_publish_and_wait.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="test-session",
            )

            from vibe3.commands.scan import _run_supervisor_scan
            from vibe3.domain import SupervisorIssueIdentified

            _run_supervisor_scan()
            mock_fetch.assert_called_once()
            mock_publish_and_wait.assert_called_once()
            event = mock_publish_and_wait.call_args.args[0]
            assert isinstance(event, SupervisorIssueIdentified)
            assert event.issue_number == 123
            assert event.actor == "cli:scan-supervisor"


class TestFailedGateBlocking:
    def test_governance_scan_ignores_failed_gate(self):
        """Manual governance scan ignores FailedGate (publishes event directly)."""
        with patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait:
            from vibe3.commands.scan import _run_governance_scan
            from vibe3.domain import GovernanceScanStarted
            from vibe3.models import ExecutionLaunchResult

            mock_publish_and_wait.return_value = ExecutionLaunchResult(
                launched=True,
                tmux_session="governance-123",
            )

            _run_governance_scan(no_async=True)
            mock_publish_and_wait.assert_called_once()
            event = mock_publish_and_wait.call_args.args[0]
            assert isinstance(event, GovernanceScanStarted)

    def test_supervisor_scan_ignores_failed_gate(self):
        """Manual supervisor scan ignores FailedGate (publishes events directly)."""
        with (
            patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
            patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        ):
            mock_fetch.return_value = (0, [])

            from vibe3.commands.scan import _run_supervisor_scan

            _run_supervisor_scan()
            mock_fetch.assert_called_once()
            # No events published for empty candidates
            mock_publish_and_wait.assert_not_called()


def test_supervisor_scan_fetches_candidates_and_publishes_events() -> None:
    """Manual supervisor scan fetches candidates and publishes events."""
    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
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
        assert mock_publish_and_wait.call_count == 2


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


def test_scan_governance_does_not_call_roles_dispatch():
    """Verify governance scan does not call dispatch_governance_execution."""
    with (
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        patch("vibe3.roles.dispatch_governance_execution") as mock_dispatch,
    ):
        from vibe3.commands.scan import _run_governance_scan
        from vibe3.models import ExecutionLaunchResult

        mock_publish_and_wait.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="governance-123",
        )

        _run_governance_scan()
        # Event published via publish_and_wait
        mock_publish_and_wait.assert_called_once()
        # Direct dispatch NOT called
        mock_dispatch.assert_not_called()


def test_scan_supervisor_does_not_call_roles_dispatch():
    """Verify supervisor scan does not call dispatch_supervisor_execution."""
    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        patch("vibe3.roles.dispatch_supervisor_execution") as mock_dispatch,
    ):
        mock_fetch.return_value = (
            1,
            [{"number": 123, "title": "Issue A", "labels": ["supervisor"]}],
        )

        from vibe3.commands.scan import _run_supervisor_scan

        _run_supervisor_scan()
        # Event published via publish_and_wait
        mock_publish_and_wait.assert_called_once()
        # Direct dispatch NOT called
        mock_dispatch.assert_not_called()


def test_supervisor_scan_shows_candidate_list_and_execution_info() -> None:
    """Manual supervisor scan shows candidate list and execution info."""
    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
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
        from vibe3.models import ExecutionLaunchResult

        mock_publish_and_wait.side_effect = [
            ExecutionLaunchResult(
                launched=True,
                tmux_session="vibe3-supervisor-123",
                backend="openai",
                model="gpt-4",
            ),
            ExecutionLaunchResult(
                launched=True,
                tmux_session="vibe3-supervisor-456",
                backend="anthropic",
                model="claude-3",
            ),
        ]

        result = runner.invoke(app, ["scan", "supervisor"])
        assert result.exit_code == 0
        assert mock_publish_and_wait.call_count == 2
        assert "Candidates:" in result.output
        assert "#123: Issue A" in result.output
        assert "#456: Issue B" in result.output
        assert "Execution:" in result.output
        assert "Backend: openai" in result.output
        assert "Model: gpt-4" in result.output
        assert "Dispatched to: vibe3-supervisor-123" in result.output
        assert "Backend: anthropic" in result.output
        assert "Model: claude-3" in result.output
        assert "Dispatched to: vibe3-supervisor-456" in result.output
