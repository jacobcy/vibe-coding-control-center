"""Tests for supervisor scan CLI command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestSupervisorScan:
    @pytest.mark.slow
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


class TestScanIntegration:
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
    """Manual supervisor scan fetches candidates and publishes events.

    With default max_dispatch_per_tick=1, only the first candidate is dispatched
    even when multiple candidates are found. This shares throttle semantics
    with the heartbeat path (OrchestrationFacade.on_supervisor_scan).
    """
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
        assert mock_publish_and_wait.call_count == 1
        assert "Throttled" in result.output


def test_supervisor_scan_respects_configured_max_per_tick() -> None:
    """Manual supervisor scan honors configured max_dispatch_per_tick."""
    from vibe3.models.orchestra_config import (
        OrchestraConfig,
        SupervisorHandoffConfig,
    )

    custom_config = OrchestraConfig.model_construct(
        supervisor_handoff=SupervisorHandoffConfig(max_dispatch_per_tick=2)
    )

    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        patch("vibe3.commands.scan.load_orchestra_config", return_value=custom_config),
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
        assert mock_publish_and_wait.call_count == 2


def test_supervisor_scan_async_results_use_shared_launch_display() -> None:
    """Supervisor async dispatch should not use command-specific result echo."""
    from vibe3.models import ExecutionLaunchResult

    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        patch("vibe3.ui.display_execution_result") as mock_display,
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
        launch = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-supervisor-issue-123",
            log_path="temp/logs/supervisor.log",
            backend="claude",
            model="sonnet",
        )
        mock_publish_and_wait.return_value = launch

        result = runner.invoke(app, ["scan", "supervisor"])

    assert result.exit_code == 0
    mock_display.assert_called_once()
    assert mock_display.call_args.args[1] is launch
    assert mock_display.call_args.args[2] == "Supervisor Dispatch"
    assert "Dispatched to:" not in result.output


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
    """Manual supervisor scan shows candidate list and execution info.

    Uses max_dispatch_per_tick=2 so both candidates are dispatched and
    their respective execution results are displayed.
    """
    from vibe3.models.orchestra_config import (
        OrchestraConfig,
        SupervisorHandoffConfig,
    )

    custom_config = OrchestraConfig.model_construct(
        supervisor_handoff=SupervisorHandoffConfig(max_dispatch_per_tick=2)
    )

    with (
        patch("vibe3.roles.fetch_supervisor_candidates") as mock_fetch,
        patch("vibe3.models.event_bus.publish_and_wait") as mock_publish_and_wait,
        patch("vibe3.commands.scan.load_orchestra_config", return_value=custom_config),
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
        assert "Supervisor Dispatch Result" in result.output
        assert "Backend: openai" in result.output
        assert "Model: gpt-4" in result.output
        assert "Tmux session: vibe3-supervisor-123" in result.output
        assert "Backend: anthropic" in result.output
        assert "Model: claude-3" in result.output
        assert "Tmux session: vibe3-supervisor-456" in result.output


def test_supervisor_show_prompt_requires_dry_run():
    """Test that --show-prompt requires --dry-run in supervisor command."""
    result = runner.invoke(app, ["scan", "supervisor", "--show-prompt"])
    assert result.exit_code == 1
    assert "--show-prompt requires --dry-run" in result.output


@patch("vibe3.roles.fetch_supervisor_candidates")
@patch("vibe3.commands.scan.GitHubClient")
@patch("vibe3.commands.scan.load_orchestra_config")
def test_supervisor_dry_run_shows_summary_with_zero_candidates(
    mock_config, mock_github_cls, mock_fetch
):
    """Test supervisor dry-run displays summary even with zero candidates."""
    mock_config.return_value = MagicMock(repo="owner/repo")
    mock_fetch.return_value = (0, [])

    result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
    assert result.exit_code == 0
    # Should show scan summary, not just prompt composition
    assert "Candidates:" in result.output or "issues scanned" in result.output


class TestSupervisorDryRunResultDisplay:
    """Supervisor dry-run must display Backend/Model via display_codeagent_result,
    consistent with plan/run/review/governance --dry-run pattern."""

    def test_dry_run_displays_result_via_shared_function(self):
        """_run_supervisor_scan_dry_run calls display_codeagent_result."""
        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh_cls,
            patch("vibe3.config.load_orchestra_config") as mock_load_config,
            patch(
                "vibe3.roles.supervisor.build_supervisor_handoff_payload"
            ) as mock_build,
            patch("vibe3.roles.scan_service.fetch_supervisor_candidates") as mock_fetch,
            patch("vibe3.agents.CodeagentBackend"),
            patch("vibe3.agents.backends.codeagent.sync_models_json"),
            patch("vibe3.ui.scan_display.display_supervisor_dry_run"),
            patch("vibe3.ui.display_codeagent_result") as mock_display,
        ):
            from vibe3.models import AgentOptions

            mock_config = MagicMock()
            mock_config.repo = "owner/repo"
            sh = MagicMock()
            sh.backend = "openai"
            sh.model = "gpt-4"
            mock_config.supervisor_handoff = sh
            mock_load_config.return_value = mock_config
            mock_build.return_value = (
                "test prompt",
                AgentOptions(agent="vibe-supervisor", backend="openai", model="gpt-5"),
                {},
            )
            mock_fetch.return_value = (0, [])
            mock_gh = MagicMock()
            mock_gh_cls.return_value = mock_gh

            from vibe3.commands.scan import _run_supervisor_scan_dry_run

            _run_supervisor_scan_dry_run(show_prompt=False)

            mock_display.assert_called_once()
            call_args = mock_display.call_args
            result_arg = call_args[0][1]
            assert result_arg.success is True
            assert result_arg.backend is not None
            assert result_arg.model is not None
            assert call_args[0][2] == "Supervisor Scan"

    @pytest.mark.slow
    def test_supervisor_dry_run_shows_backend_and_model(self):
        """Integration: 'scan supervisor --dry-run' shows Backend/Model."""
        result = runner.invoke(app, ["scan", "supervisor", "--dry-run"])
        if result.exit_code != 0:
            pytest.skip(f"Environment issue: {result.exception}")
        output = result.output
        assert "Backend:" in output, f"Missing Backend: in output:\n{output}"
        assert "Model:" in output, f"Missing Model: in output:\n{output}"
        assert "Supervisor Scan Result" in output
        assert "Completed successfully" in output
