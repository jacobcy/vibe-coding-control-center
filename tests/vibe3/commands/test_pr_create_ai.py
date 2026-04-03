"""Integration tests for PR create command with AI support."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.config.settings import AIConfig


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestPRCreateCommandAI:
    """Tests for PR create command with --ai flag."""

    def test_pr_create_confirms_existing_pr(self, runner: CliRunner) -> None:
        """Existing PR should be confirmed without requiring title."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            existing_pr = MagicMock(
                number=456,
                title="Existing PR",
                body="",
                model_dump=lambda: {"number": 456, "title": "Existing PR"},
            )
            mock_service.return_value.get_pr.return_value = existing_pr

            result = runner.invoke(app, ["pr", "create", "--json", "--yes"])

        assert result.exit_code == 0
        assert json.loads(result.output)["number"] == 456
        mock_service.return_value.sync_pr_state_from_remote.assert_called_once_with(
            existing_pr, actor=None
        )
        mock_service.return_value.create_draft_pr.assert_not_called()

    def test_pr_create_existing_pr_shows_confirmed_status(
        self, runner: CliRunner
    ) -> None:
        """Non-JSON output should report existing PR status instead of created."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            existing_pr = MagicMock(
                number=456,
                title="Existing PR",
                body="",
                state=MagicMock(value="MERGED"),
                draft=False,
                url="https://github.com/org/repo/pull/456",
                head_branch="task/311",
                base_branch="main",
            )
            mock_service.return_value.get_pr.return_value = existing_pr

            result = runner.invoke(app, ["pr", "create", "--yes"])

        assert result.exit_code == 0
        assert "already exists and is merged" in result.output.lower()

    def test_pr_create_requires_yes_flag(self, runner: CliRunner) -> None:
        """PR create should exit with a warning if --yes is not provided."""
        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        assert "此命令仅建议人类使用" in result.output

    def test_pr_create_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create without --ai flag works normally."""
        with (
            patch(
                "vibe3.commands.pr_create.FlowService.get_current_branch",
                return_value="task/demo",
            ),
            patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="main",
            ),
            patch("vibe3.services.pr_create_usecase.PRCreateUsecase.check_flow_task"),
            patch("vibe3.commands.pr_create.PRService") as mock_service,
        ):
            mock_service.return_value.get_pr.return_value = None
            mock_service.return_value.create_draft_pr.return_value = MagicMock(
                number=123,
                title="Test PR",
                body="Test body",
                model_dump=lambda: {"number": 123, "title": "Test PR"},
            )
            result = runner.invoke(app, ["pr", "create", "-t", "Test PR", "--yes"])
        assert result.exit_code == 0
        mock_service.return_value.create_draft_pr.assert_called_once_with(
            title="Test PR",
            body="",
            base_branch="main",
            actor=None,
        )

    def test_pr_create_ai_disabled(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create with --ai when AI is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.get_pr.return_value = None
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="Test PR",
                    body="Test body",
                    model_dump=lambda: {"number": 123},
                )
                with patch(
                    "vibe3.services.pr_create_usecase.VibeConfig.get_defaults"
                ) as mock_config:
                    mock_config.return_value.ai.enabled = False
                    result = runner.invoke(app, ["pr", "create", "--ai", "--yes"])
                    # Should fail because title missing and AI disabled
                    assert result.exit_code != 0

    def test_pr_create_ai_json_uses_suggestions_without_prompt(
        self, runner: CliRunner
    ) -> None:
        """Test pr create --ai --json uses AI result without prompting."""
        with patch(
            "vibe3.commands.pr_create.FlowService.get_current_branch",
            return_value="task/refactor/v3-thin-commands-19k",
        ):
            with patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="origin/main",
            ):
                with patch(
                    "vibe3.services.pr_create_usecase.BaseResolutionUsecase.collect_branch_material"
                ) as mock_material:
                    mock_material.return_value = MagicMock(
                        commits=["feat: add feature"],
                        changed_files=["src/file.py"],
                    )
                    with patch(
                        "vibe3.services.pr_create_usecase.VibeConfig.get_defaults"
                    ) as mock_config:
                        mock_config.return_value.ai = AIConfig()
                        with patch(
                            "vibe3.services.pr_create_usecase.AIService.suggest_pr_content"
                        ) as mock_suggest:
                            mock_suggest.return_value = (
                                "feat: ai title",
                                "Summary\n\n- change",
                            )
                            with (
                                patch(
                                    "vibe3.services.pr_create_usecase.PRCreateUsecase.check_flow_task"
                                ),
                                patch(
                                    "vibe3.commands.pr_create.PRService"
                                ) as mock_service,
                            ):
                                mock_service.return_value.get_pr.return_value = None
                                mock_pr = MagicMock(
                                    number=123,
                                    title="feat: ai title",
                                    body="Summary\n\n- change",
                                    model_dump=lambda: {
                                        "number": 123,
                                        "title": "feat: ai title",
                                        "body": "Summary\n\n- change",
                                    },
                                )
                                (
                                    mock_service.return_value.create_draft_pr.return_value
                                ) = mock_pr
                                result = runner.invoke(
                                    app,
                                    ["pr", "create", "--ai", "--json", "--yes"],
                                )

        assert result.exit_code == 0
        assert json.loads(result.output)["title"] == "feat: ai title"
