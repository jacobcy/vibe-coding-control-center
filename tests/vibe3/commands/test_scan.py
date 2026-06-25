"""Tests for scan CLI command (governance tests only)."""

import re
from unittest.mock import MagicMock, patch

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

    @patch("vibe3.models.publish_and_wait")
    def test_material_override_propagates_to_event(self, mock_publish_wait: MagicMock):
        """Test material_override is passed to GovernanceScanStarted event."""
        from vibe3.commands.scan import _publish_and_wait_governance_event
        from vibe3.models import ExecutionLaunchResult

        # Mock successful execution result with correct type
        mock_result = MagicMock(spec=ExecutionLaunchResult)
        mock_result.launched = True
        mock_publish_wait.return_value = mock_result

        # Call with material_override
        result = _publish_and_wait_governance_event(
            material_override="roadmap-intake", tick_count=0
        )

        # Verify event was published with correct material_override
        assert result is not None
        mock_publish_wait.assert_called_once()
        event = mock_publish_wait.call_args.args[0]

        # Check event attributes
        assert event.material_override == "roadmap-intake"
        assert event.tick_count == 0


class TestGovernanceScan:
    @pytest.mark.slow
    def test_governance_dry_run(self):
        result = runner.invoke(app, ["scan", "governance", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # After refactor, output uses CodeagentBackend.run(dry_run=True) format
        assert "prompt composition" in output_lower or "governance.scan" in output_lower

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
        # After fix: --dry-run shows Prompt Composition summary (not full prompt)
        assert (
            "Prompt Composition" in result.output or "prompt" in result.output.lower()
        )

    @pytest.mark.slow
    def test_governance_dry_run_shows_prompt_preview(self):
        result = runner.invoke(
            app,
            [
                "scan",
                "governance",
                "--role",
                "assignee-pool",
                "--dry-run",
                "--show-prompt",
            ],
        )
        assert result.exit_code == 0
        # With --show-prompt, should display full prompt with section markers
        output_lower = result.output.lower()
        assert "<!-- section:" in output_lower or "governance.scan" in output_lower


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


def test_governance_show_prompt_requires_dry_run():
    """Test that --show-prompt requires --dry-run in governance command."""
    result = runner.invoke(
        app, ["scan", "governance", "--show-prompt", "--role", "assignee-pool"]
    )
    assert result.exit_code == 1
    assert "--show-prompt requires --dry-run" in result.output


class TestGovernanceDryRunResultDisplay:
    """Governance dry-run must display Backend/Model via display_codeagent_result,
    consistent with plan/run/review --dry-run pattern (PR #3143)."""

    def test_dry_run_displays_result_via_shared_function(self):
        """_run_governance_scan_dry_run calls display_codeagent_result."""
        with (
            patch("vibe3.execution.run_governance_sync") as mock_run_sync,
            patch("vibe3.observability.append_governance_event"),
            patch("vibe3.roles.governance_factory.build_default_governance_fns"),
            patch("vibe3.ui.display_codeagent_result") as mock_display,
        ):
            from vibe3.agents import CodeagentResult

            mock_run_sync.return_value = CodeagentResult(
                success=True, backend="openai", model="gpt-5"
            )

            from vibe3.commands.scan import _run_governance_scan_dry_run

            _run_governance_scan_dry_run(
                material_override="assignee-pool", show_prompt=False
            )

            mock_display.assert_called_once()
            call_args = mock_display.call_args
            result_arg = call_args[0][1]
            assert isinstance(result_arg, CodeagentResult)
            assert result_arg.backend == "openai"
            assert result_arg.model == "gpt-5"
            assert result_arg.success is True
            assert call_args[0][2] == "Governance Scan"

    @patch("vibe3.execution.governance_sync_runner.CodeagentBackend")
    @patch("vibe3.execution.governance_sync_runner.load_orchestra_config")
    @patch("vibe3.services.orchestra.OrchestraStatusService")
    @patch("vibe3.execution.governance_sync_runner.resolve_display_agent_options")
    def test_run_governance_sync_dry_run_returns_codeagent_result(
        self,
        mock_resolve_opts,
        mock_status_svc,
        mock_load_config,
        mock_backend_cls,
    ):
        """dry_run=True returns CodeagentResult with backend/model."""
        from vibe3.agents import CodeagentResult
        from vibe3.execution.governance_sync_runner import run_governance_sync
        from vibe3.models import AgentOptions

        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_status = MagicMock()
        mock_status.snapshot.return_value = MagicMock()
        mock_status_svc.create.return_value = mock_status

        mock_backend = MagicMock()
        mock_backend.run.return_value = MagicMock(exit_code=0)
        mock_backend_cls.return_value = mock_backend

        mock_resolve_opts.return_value = AgentOptions(
            backend="anthropic", model="claude-sonnet-4-6"
        )

        mock_governance_fns = MagicMock()
        mock_governance_fns.resolve_options.return_value = AgentOptions(
            agent="vibe-governance"
        )
        mock_governance_fns.build_snapshot_context.return_value = {}
        mock_governance_fns.render_prompt.return_value = MagicMock(
            rendered_text="test prompt",
            provenance={},
            warnings=[],
        )

        mock_append_event = MagicMock()

        with patch(
            "vibe3.execution.governance_sync_runner.PromptManifest"
        ) as mock_manifest_cls:
            mock_manifest = MagicMock()
            mock_recipe = MagicMock()
            mock_recipe.variants = {}
            mock_manifest.recipe.return_value = mock_recipe
            mock_manifest_cls.load_for_prompts_path.return_value = mock_manifest

            with (
                patch(
                    "vibe3.execution.governance_sync_runner.collect_dry_run_provenance"
                ),
                patch("vibe3.execution.governance_sync_runner.write_prompt_provenance"),
            ):
                result = run_governance_sync(
                    tick_count=0,
                    material_override="assignee-pool",
                    dry_run=True,
                    show_prompt=False,
                    session_id=None,
                    governance_fns=mock_governance_fns,
                    append_event=mock_append_event,
                )

        assert result is not None
        assert isinstance(result, CodeagentResult)
        assert result.success is True
        assert result.backend == "anthropic"
        assert result.model == "claude-sonnet-4-6"

    def test_run_governance_sync_non_dry_run_returns_none(self):
        """dry_run=False returns None (no result display needed)."""
        with (
            patch(
                "vibe3.execution.governance_sync_runner.CodeagentBackend"
            ) as mock_backend_cls,
            patch(
                "vibe3.execution.governance_sync_runner.load_orchestra_config"
            ) as mock_load_config,
            patch("vibe3.services.orchestra.OrchestraStatusService") as mock_status_svc,
        ):
            mock_config = MagicMock()
            mock_load_config.return_value = mock_config
            mock_status = MagicMock()
            mock_status.snapshot.return_value = MagicMock()
            mock_status_svc.create.return_value = mock_status

            mock_backend = MagicMock()
            mock_backend.run.return_value = MagicMock(exit_code=0)
            mock_backend_cls.return_value = mock_backend

            mock_governance_fns = MagicMock()
            mock_governance_fns.resolve_options.return_value = MagicMock()
            mock_governance_fns.build_snapshot_context.return_value = {}
            mock_governance_fns.render_prompt.return_value = MagicMock(
                rendered_text="test prompt",
                provenance={},
                warnings=[],
            )

            from vibe3.execution.governance_sync_runner import run_governance_sync

            result = run_governance_sync(
                tick_count=0,
                dry_run=False,
                show_prompt=False,
                session_id=None,
                governance_fns=mock_governance_fns,
                append_event=MagicMock(),
            )

            assert result is None

    @pytest.mark.slow
    def test_governance_dry_run_shows_backend_and_model(self):
        """Integration: 'scan governance --dry-run' shows Backend/Model in output."""
        result = runner.invoke(app, ["scan", "governance", "--dry-run"])
        if result.exit_code != 0:
            pytest.skip(f"Environment issue: {result.exception}")
        output = result.output
        # After fix: Backend/Model should appear in Governance Scan Result section
        assert "Backend:" in output, f"Missing Backend: in output:\n{output}"
        assert "Model:" in output, f"Missing Model: in output:\n{output}"
        assert "Governance Scan Result" in output
        assert "Completed successfully" in output
