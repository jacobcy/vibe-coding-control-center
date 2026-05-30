"""Tests for review command assembler integration and CLI surface.

Merged from test_review.py + test_review_help.py (non-removal tests).
Removal tests from test_review_help.py are in test_removed_commands.py.
"""

from __future__ import annotations

import re
from unittest.mock import patch

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
        from vibe3.agents import make_review_context_builder
        from vibe3.config.settings import VibeConfig
        from vibe3.models.review import ReviewRequest, ReviewScope

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


def test_review_no_args_shows_help():
    """vibe review (no subcommand) -> shows help.

    Exit 0 or 2 per typer no_args_is_help.
    """
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "base" in result.output


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
        with (
            patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
            patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
            patch("vibe3.commands.review.build_base_review_request") as mock_request,
            patch("vibe3.commands.review.execute_manual_review_sync") as mock_execute,
        ):
            mock_flow.return_value = (object(), "feature/test")
            mock_base.return_value.resolve_review_base.return_value = type(
                "ResolvedBase",
                (),
                {"base_branch": "main", "auto_detected": False},
            )()
            mock_request.return_value = (object(), 123, None)
            mock_execute.return_value = type(
                "Result",
                (),
                {"verdict": "MINOR", "handoff_file": None},
            )()

            result = runner.invoke(app, ["base", "main", "--no-async"])

        assert result.exit_code == 0

    def test_refuse_verdict_exits_nonzero(self) -> None:
        with (
            patch("vibe3.commands.review.ensure_flow_for_current_branch") as mock_flow,
            patch("vibe3.commands.review.build_base_resolution_usecase") as mock_base,
            patch("vibe3.commands.review.build_base_review_request") as mock_request,
            patch("vibe3.commands.review.execute_manual_review_sync") as mock_execute,
        ):
            mock_flow.return_value = (object(), "feature/test")
            mock_base.return_value.resolve_review_base.return_value = type(
                "ResolvedBase",
                (),
                {"base_branch": "main", "auto_detected": False},
            )()
            mock_request.return_value = (object(), 123, None)
            mock_execute.return_value = type(
                "Result",
                (),
                {"verdict": "REFUSE", "handoff_file": None},
            )()

            result = runner.invoke(app, ["base", "main", "--no-async"])

        assert result.exit_code == 1
