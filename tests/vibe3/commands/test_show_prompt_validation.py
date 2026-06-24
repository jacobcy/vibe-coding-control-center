"""Tests for --show-prompt requires --dry-run validation."""

from unittest.mock import MagicMock, patch

import pytest
from click.exceptions import Exit
from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.commands.command_options import validate_show_prompt_dependency

runner = CliRunner(env={"NO_COLOR": "1"})


class TestValidateShowPromptDependency:
    """Unit tests for the validation helper function."""

    def test_rejects_show_prompt_without_dry_run(self):
        """Should exit with error when --show-prompt is used without --dry-run."""
        # typer.Exit is click.exceptions.Exit, which is a subclass of SystemExit
        with pytest.raises(Exit) as exc_info:
            validate_show_prompt_dependency(dry_run=False, show_prompt=True)

        assert exc_info.value.exit_code == 1

    def test_allows_show_prompt_with_dry_run(self):
        """Should not raise when --show-prompt is used with --dry-run."""
        # Should not raise
        validate_show_prompt_dependency(dry_run=True, show_prompt=True)

    def test_allows_no_show_prompt_without_dry_run(self):
        """Should not raise when --show-prompt is not used."""
        # Should not raise
        validate_show_prompt_dependency(dry_run=False, show_prompt=False)

    def test_allows_no_show_prompt_with_dry_run(self):
        """Should not raise when only --dry-run is used."""
        # Should not raise
        validate_show_prompt_dependency(dry_run=True, show_prompt=False)


class TestRunCommandValidation:
    """Integration tests for run command validation."""

    def test_run_rejects_show_prompt_without_dry_run(self):
        """run command should reject --show-prompt without --dry-run."""
        # Patch dependencies to avoid real execution
        with (
            patch(
                "vibe3.commands.run.resolve_branch_arg", return_value="task/issue-42"
            ),
            patch(
                "vibe3.commands.run.validate_run_prerequisites",
                return_value=(MagicMock(), 42),
            ),
        ):
            result = runner.invoke(cli_app, ["run", "test", "--show-prompt"])

        assert result.exit_code == 1
        assert "Error: --show-prompt requires --dry-run" in result.output

    def test_run_show_prompt_with_dry_run_still_works(self):
        """run command should accept --show-prompt with --dry-run."""
        # Patch dependencies to avoid real execution
        with (
            patch(
                "vibe3.commands.run.resolve_branch_arg", return_value="task/issue-42"
            ),
            patch(
                "vibe3.commands.run.validate_run_prerequisites",
                return_value=(MagicMock(), 42),
            ),
            patch("vibe3.domain.publish"),
        ):
            result = runner.invoke(
                cli_app, ["run", "test", "--dry-run", "--show-prompt", "--no-async"]
            )

        # Validation should pass, but command may fail for other
        # reasons (missing flow, etc.). The key is that we should
        # NOT see the validation error
        assert "Error: --show-prompt requires --dry-run" not in result.output


class TestPlanCommandValidation:
    """Integration tests for plan command validation."""

    def test_plan_rejects_show_prompt_without_dry_run(self):
        """plan command should reject --show-prompt without --dry-run."""
        with (
            patch("vibe3.commands.plan._plan_for_branch") as mock_plan,
            patch(
                "vibe3.commands.plan.resolve_branch_arg", return_value="task/issue-42"
            ),
        ):
            result = runner.invoke(cli_app, ["plan", "--branch", "42", "--show-prompt"])

        assert result.exit_code == 1
        assert "Error: --show-prompt requires --dry-run" in result.output
        # Mock should NOT be called since validation happens first
        mock_plan.assert_not_called()

    def test_plan_show_prompt_with_dry_run_still_works(self):
        """plan command should accept --show-prompt with --dry-run."""
        with patch("vibe3.commands.plan.FlowService") as mock_flow_service:
            # Setup mock to avoid hitting real flow state
            mock_flow_instance = mock_flow_service.return_value
            mock_flow_instance.get_flow_status.return_value = None

            result = runner.invoke(
                cli_app, ["plan", "--branch", "42", "--dry-run", "--show-prompt"]
            )

        # Should exit with error about missing flow, NOT about --show-prompt
        assert "Error: --show-prompt requires --dry-run" not in result.output


class TestReviewCommandValidation:
    """Integration tests for review command validation."""

    def test_review_rejects_show_prompt_without_dry_run(self):
        """review command should reject --show-prompt without --dry-run."""
        with (
            patch("vibe3.commands.review._review_branch_impl") as mock_review,
            patch(
                "vibe3.commands.review.resolve_branch_arg", return_value="task/issue-42"
            ),
        ):
            result = runner.invoke(
                cli_app, ["review", "--branch", "42", "--show-prompt"]
            )

        assert result.exit_code == 1
        assert "Error: --show-prompt requires --dry-run" in result.output
        # Mock should NOT be called since validation happens first
        mock_review.assert_not_called()

    @pytest.mark.slow
    def test_review_show_prompt_with_dry_run_still_works(self):
        """review command should accept --show-prompt with --dry-run."""
        with patch(
            "vibe3.commands.review.validate_review_prerequisites"
        ) as mock_validate:
            # Setup mock to allow validation to pass
            mock_validate.return_value = (None, 42)

            with patch("vibe3.execution.issue_role_sync_runner.run_issue_role_sync"):
                result = runner.invoke(
                    cli_app,
                    [
                        "review",
                        "--branch",
                        "42",
                        "--dry-run",
                        "--show-prompt",
                        "--no-async",
                    ],
                )

        # Should exit 0, not with validation error
        assert "Error: --show-prompt requires --dry-run" not in result.output


class TestReviewBaseCommandValidation:
    """Integration tests for review base subcommand validation."""

    def test_review_base_rejects_show_prompt_without_dry_run(self):
        """review base command should reject --show-prompt without --dry-run."""
        with patch(
            "vibe3.commands.review.ensure_flow_for_current_branch"
        ) as mock_ensure:
            # Setup mock to avoid needing real flow
            mock_ensure.return_value = (None, "test-branch")

            result = runner.invoke(cli_app, ["review", "base", "main", "--show-prompt"])

        assert result.exit_code == 1
        assert "Error: --show-prompt requires --dry-run" in result.output

    def test_review_base_show_prompt_with_dry_run_still_works(self):
        """review base command should accept --show-prompt with --dry-run."""
        with (
            patch(
                "vibe3.commands.review.ensure_flow_for_current_branch"
            ) as mock_ensure,
            patch("vibe3.domain.publish"),
        ):
            # Setup mock to avoid needing real flow
            mock_ensure.return_value = (None, "test-branch")

            with patch(
                "vibe3.commands.review.build_base_resolution_usecase"
            ) as mock_base_usecase:
                resolved = (
                    mock_base_usecase.return_value.resolve_review_base.return_value
                )
                resolved.auto_detected = False
                resolved.base_branch = "main"

                with patch(
                    "vibe3.commands.review.build_base_review_request"
                ) as mock_build:
                    mock_build.return_value = (None, None, None)

                    result = runner.invoke(
                        cli_app,
                        [
                            "review",
                            "base",
                            "main",
                            "--dry-run",
                            "--show-prompt",
                        ],
                    )

        # Should exit 0, not with validation error
        assert "Error: --show-prompt requires --dry-run" not in result.output


class TestInternalManagerCommandValidation:
    """Integration tests for internal manager command validation."""

    def test_internal_manager_rejects_show_prompt_without_dry_run(self, monkeypatch):
        """internal manager command should reject --show-prompt without --dry-run."""
        monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as mock_run:
            result = runner.invoke(
                cli_app, ["internal", "manager", "123", "--show-prompt", "--no-async"]
            )

        assert result.exit_code == 1
        assert "Error: --show-prompt requires --dry-run" in result.output
        # Mock should NOT be called since validation happens first
        mock_run.assert_not_called()

    def test_internal_manager_show_prompt_with_dry_run_still_works(self, monkeypatch):
        """internal manager command should accept --show-prompt with --dry-run."""
        monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")
        with patch(
            "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
        ) as mock_run:
            result = runner.invoke(
                cli_app,
                [
                    "internal",
                    "manager",
                    "123",
                    "--dry-run",
                    "--show-prompt",
                    "--no-async",
                ],
            )

        assert result.exit_code == 0
        # Mock should be called since validation passed
        mock_run.assert_called_once()
