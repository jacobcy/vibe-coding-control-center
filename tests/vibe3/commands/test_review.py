"""Tests for review command assembler integration and CLI surface.

Merged from test_review.py + test_review_help.py (non-removal tests).
Removal tests from test_review_help.py are in test_removed_commands.py.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI color codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


# ==============================================================================
# Review context builder tests (from test_review.py)
# ==============================================================================


class TestReviewContextBuilderUsesAssembler:
    """Assert review context builders go through PromptAssembler."""

    def test_make_review_context_builder_calls_body_builder(self) -> None:
        """make_review_context_builder should invoke build_review_prompt_body."""
        from vibe3.agents.review_prompt import make_review_context_builder
        from vibe3.config.settings import VibeConfig
        from vibe3.models import ReviewRequest, ReviewScope

        config = VibeConfig.get_defaults()
        request = ReviewRequest(scope=ReviewScope.for_base("main"))
        with patch(
            "vibe3.agents.review_prompt.build_review_prompt_body",
            return_value="assembled review body",
        ):
            cb = make_review_context_builder(request, config)
            text = cb()

        assert text == "assembled review body"
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "review.default"

    def test_review_context_builder_no_longer_exports_build_review_context(
        self,
    ) -> None:
        """build_review_context (old name) must not exist as public API."""
        import vibe3.agents.review_prompt as mod

        assert not hasattr(
            mod, "build_review_context"
        ), "build_review_context should be deleted; use build_review_prompt_body"

    def test_execute_manual_review_lives_in_role_layer(self) -> None:
        """Manual review execution should now be owned by roles.review."""
        import vibe3.roles.review as mod

        assert hasattr(mod, "execute_manual_review_async")
        assert hasattr(mod, "execute_manual_review_sync")


# ==============================================================================
# Review CLI help/surface tests (from test_review_help.py, non-removal)
# ==============================================================================


def test_review_no_arg_defaults_to_current_branch():
    """vibe review (no subcommand) -> executes review on current branch."""
    with (
        patch("vibe3.commands.review.validate_review_prerequisites") as mock_validate,
        patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
        ) as mock_async,
        patch("vibe3.commands.review.resolve_branch_arg") as mock_resolve,
        patch("vibe3.commands.review._check_report_ref", return_value=True),
    ):
        mock_flow = MagicMock()
        mock_flow.task_issue_number = 42
        mock_validate.return_value = (mock_flow, 42)
        mock_resolve.return_value = "task/issue-42"

        result = runner.invoke(app, [])

    assert result.exit_code == 0
    # resolve_branch_arg is called with (None, flow_service=<FlowService instance>)
    mock_resolve.assert_called_once()
    assert mock_resolve.call_args[0][0] is None
    assert "flow_service" in mock_resolve.call_args[1]
    mock_async.assert_called_once()


def test_review_help_only_shows_supported_commands():
    """vibe review --help should only show supported command: base.

    Removed commands: commit, uncommitted, analyze-commit, pr
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Supported commands
    assert "base" in result.output
    # Removed commands - should NOT appear as command names
    assert "commit" not in result.output.lower()
    assert "uncommitted" not in result.output.lower()
    assert "analyze-commit" not in result.output.lower()
    # Check Commands section specifically
    lines = result.output.split("\n")
    commands_section = False
    for line in lines:
        if "Commands" in line:
            commands_section = True
            continue
        if commands_section and line.strip():
            # In Commands section, check no 'pr' command listed
            assert not line.strip().startswith("pr")
    assert "--message" not in result.output


def test_review_base_help_mentions_dry_run_option():
    """vibe review base --help should mention --dry-run option."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    # Strip ANSI codes before checking
    output = _strip_ansi(result.output)
    assert "--dry-run" in output
    assert "--message" not in output


class TestReviewBaseExitCodes:
    """Verify review base exit codes follow verdict semantics."""

    def test_minor_verdict_does_not_exit_nonzero(self) -> None:
        from vibe3.models import ReviewRequest, ReviewScope
        from vibe3.roles.review_helpers import ReviewRunResult

        with (
            patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
            patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
            patch("vibe3.commands.review.build_base_review_request") as mock_request,
            patch("vibe3.config.config_loader.load_config_for_role") as _mock_config,
            patch("vibe3.roles.review.execute_manual_review_sync") as mock_execute,
            patch("vibe3.roles.execute_manual_review_sync") as mock_execute_cache,
            patch(
                "vibe3.clients.git_status_ops.get_changed_files",
                return_value=["test.py"],
            ) as _mock_changes,
        ):
            # Create a mock flow_service with get_flow_status method
            mock_flow_service = MagicMock()
            mock_flow_service.get_flow_status.return_value = None  # No flow state
            mock_flow.return_value = (mock_flow_service, "feature/test")
            mock_base.return_value.resolve_review_base.return_value = type(
                "ResolvedBase",
                (),
                {"base_branch": "main", "auto_detected": False},
            )()
            # Create proper ReviewRequest instance
            review_request = ReviewRequest(scope=ReviewScope.for_base("main"))
            mock_request.return_value = (review_request, 123, None)
            mock_execute.return_value = ReviewRunResult(
                verdict="MINOR",
                handoff_file=None,
                issue_number=None,
            )
            mock_execute_cache.return_value = mock_execute.return_value

            result = runner.invoke(app, ["base", "main", "--no-async", "--yes"])

        assert result.exit_code == 0

    def test_refuse_verdict_exits_nonzero(self) -> None:

        from vibe3.models import ReviewRequest, ReviewScope
        from vibe3.roles.review_helpers import ReviewRunResult

        with (
            patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
            patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
            patch("vibe3.commands.review.build_base_review_request") as mock_request,
            patch("vibe3.config.config_loader.load_config_for_role") as _mock_config,
            patch("vibe3.roles.review.execute_manual_review_sync") as mock_execute,
            patch("vibe3.roles.execute_manual_review_sync") as mock_execute_cache,
            patch(
                "vibe3.clients.git_status_ops.get_changed_files",
                return_value=["test.py"],
            ) as _mock_changes,
        ):
            # Create a mock flow_service with get_flow_status method
            mock_flow_service = MagicMock()
            mock_flow_service.get_flow_status.return_value = None  # No flow state
            mock_flow.return_value = (mock_flow_service, "feature/test")
            mock_base.return_value.resolve_review_base.return_value = type(
                "ResolvedBase",
                (),
                {"base_branch": "main", "auto_detected": False},
            )()
            # Create proper ReviewRequest instance
            review_request = ReviewRequest(scope=ReviewScope.for_base("main"))
            mock_request.return_value = (review_request, 123, None)
            mock_execute.return_value = ReviewRunResult(
                verdict="REFUSE",
                handoff_file=None,
                issue_number=None,
            )
            mock_execute_cache.return_value = mock_execute.return_value

            result = runner.invoke(app, ["base", "main", "--no-async", "--yes"])

        assert result.exit_code == 1

    def test_handler_exception_results_in_error_verdict(self) -> None:
        """A crash inside execute_manual_review_sync must surface as
        verdict=ERROR + exit 1, not a silent exit 0 (CRITICAL #2 fix)."""

        from vibe3.models import ReviewRequest, ReviewScope

        with (
            patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
            patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
            patch("vibe3.commands.review.build_base_review_request") as mock_request,
            patch("vibe3.config.config_loader.load_config_for_role") as _mock_config,
            patch("vibe3.roles.review.execute_manual_review_sync") as mock_execute,
            patch("vibe3.roles.execute_manual_review_sync") as mock_execute_cache,
        ):
            # Create a mock flow_service with get_flow_status method
            mock_flow_service = MagicMock()
            mock_flow_service.get_flow_status.return_value = None  # No flow state
            mock_flow.return_value = (mock_flow_service, "feature/test")
            mock_base.return_value.resolve_review_base.return_value = type(
                "ResolvedBase",
                (),
                {"base_branch": "main", "auto_detected": False},
            )()
            # Create proper ReviewRequest instance
            review_request = ReviewRequest(scope=ReviewScope.for_base("main"))
            mock_request.return_value = (review_request, 123, None)
            mock_execute.side_effect = RuntimeError("simulated review crash")
            mock_execute_cache.side_effect = mock_execute.side_effect

            result = runner.invoke(app, ["base", "main", "--no-async", "--yes"])

        assert result.exit_code == 1
        assert "=== Verdict: ERROR ===" in _strip_ansi(result.output)


def test_review_base_help_mentions_show_prompt_option():
    """vibe review base --help should mention --show-prompt option."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    # Strip ANSI codes before checking
    output = _strip_ansi(result.output)
    assert "--show-prompt" in output


def test_review_base_show_prompt_forwarded_to_sync():
    """review base --show-prompt should forward the flag to
    execute_manual_review_sync (requires --dry-run)."""
    from vibe3.models import ReviewRequest, ReviewScope
    from vibe3.roles.review_helpers import ReviewRunResult

    with (
        patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
        patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
        patch("vibe3.commands.review.build_base_review_request") as mock_request,
        patch("vibe3.config.config_loader.load_config_for_role") as _mock_config,
        patch("vibe3.roles.review.execute_manual_review_sync") as mock_execute,
        patch("vibe3.roles.execute_manual_review_sync") as mock_execute_cache,
        patch(
            "vibe3.clients.git_status_ops.get_changed_files", return_value=["test.py"]
        ) as _mock_changes,
    ):
        # Create a mock flow_service with get_flow_status method
        mock_flow_service = MagicMock()
        mock_flow_service.get_flow_status.return_value = None  # No flow state
        mock_flow.return_value = (mock_flow_service, "feature/test")
        mock_base.return_value.resolve_review_base.return_value = type(
            "ResolvedBase",
            (),
            {"base_branch": "main", "auto_detected": False},
        )()
        # Create proper ReviewRequest instance
        review_request = ReviewRequest(scope=ReviewScope.for_base("main"))
        mock_request.return_value = (review_request, 123, None)
        mock_execute.return_value = ReviewRunResult(
            verdict="MINOR",
            handoff_file=None,
            issue_number=None,
        )
        mock_execute_cache.return_value = mock_execute.return_value

        result = runner.invoke(
            app, ["base", "main", "--no-async", "--yes", "--dry-run", "--show-prompt"]
        )

    assert result.exit_code == 0
    # Handler resolves via vibe3.roles (cache), not vibe3.roles.review
    assert mock_execute_cache.call_args.kwargs["show_prompt"] is True


def test_review_help_shows_new_options():
    """review --help should show --agent, --backend, --model, --fresh-session."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "--agent" in output
    assert "--backend" in output
    assert "--model" in output
    assert "--fresh-session" in output


def test_review_base_help_shows_new_options():
    """review base --help should show --agent, --backend, --model, --fresh-session."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "--agent" in output
    assert "--backend" in output
    assert "--model" in output
    assert "--fresh-session" in output


def test_review_fresh_session_propagates():
    """review --fresh-session should propagate to run_issue_role_sync."""
    with (
        patch("vibe3.commands.review.validate_review_prerequisites") as mock_validate,
        patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as mock_sync,
        patch("vibe3.commands.review.resolve_branch_arg") as mock_resolve,
        patch("vibe3.commands.review._check_report_ref", return_value=True),
    ):
        mock_flow = MagicMock()
        mock_flow.task_issue_number = 42
        mock_validate.return_value = (mock_flow, 42)
        mock_resolve.return_value = "task/issue-42"

        result = runner.invoke(app, ["--no-async", "--fresh-session"])

    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args.kwargs
    assert call_kwargs["fresh_session"] is True


@pytest.mark.parametrize(
    ("cli_args", "kwarg_name", "expected_value"),
    [
        (["--agent", "foo"], "agent", "foo"),
        (["--backend", "claude"], "backend", "claude"),
        (
            ["--backend", "claude", "--model", "claude-opus-4-8"],
            "model",
            "claude-opus-4-8",
        ),
    ],
)
def test_review_cli_option_propagates(
    cli_args: list[str], kwarg_name: str, expected_value: str
) -> None:
    """review --agent/--backend/--model should propagate to run_issue_role_sync."""
    mock_config = MagicMock()
    with (
        patch("vibe3.commands.review.validate_review_prerequisites") as mock_validate,
        patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as _mock_sync,
        patch("vibe3.execution.run_issue_role_sync") as mock_sync_cache,
        patch("vibe3.commands.review.resolve_branch_arg") as mock_resolve,
        patch("vibe3.commands.review._check_report_ref", return_value=True),
    ):
        import vibe3.config

        vibe3.config.load_config_for_role = lambda *a, **kw: mock_config
        try:
            mock_flow = MagicMock()
            mock_flow.task_issue_number = 42
            mock_validate.return_value = (mock_flow, 42)
            mock_resolve.return_value = "task/issue-42"

            result = runner.invoke(app, ["--no-async", *cli_args])
        finally:
            del vibe3.config.load_config_for_role

    assert result.exit_code == 0
    mock_sync_cache.assert_called_once()
    call_kwargs = mock_sync_cache.call_args.kwargs
    assert call_kwargs[kwarg_name] == expected_value
