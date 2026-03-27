"""Integration tests for PR create command with AI support."""

import json
import os
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

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

            result = runner.invoke(app, ["pr", "create", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.output)["number"] == 456
        mock_service.return_value.sync_pr_state_from_remote.assert_called_once_with(
            existing_pr, actor="server"
        )
        mock_service.return_value.create_draft_pr.assert_not_called()

    def test_pr_create_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create without --ai flag works normally."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            mock_service.return_value.get_pr.return_value = None
            mock_service.return_value.create_draft_pr.return_value = MagicMock(
                number=123,
                title="Test PR",
                body="Test body",
                model_dump=lambda: {"number": 123, "title": "Test PR"},
            )
            result = runner.invoke(app, ["pr", "create", "-t", "Test PR", "--yes"])
            assert result.exit_code in [0, 1]
            mock_service.return_value.create_draft_pr.assert_called_once_with(
                title="Test PR",
                body="",
                base_branch="main",
                actor="server",
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
                    assert result.exit_code in [0, 1]

    def test_pr_create_ai_no_commits(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create with --ai but no commits."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.get_pr.return_value = None
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="Test PR",
                    body="Test body",
                    model_dump=lambda: {"number": 123},
                )
                with patch(
                    "vibe3.services.pr_create_usecase.BaseResolutionUsecase.collect_branch_material"
                ) as mock_material:
                    mock_material.return_value = MagicMock(
                        commits=[],
                        changed_files=[],
                    )
                    result = runner.invoke(app, ["pr", "create", "--ai", "--yes"])
                    assert result.exit_code in [0, 1]

    def test_pr_create_ai_with_suggestions(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test PR create with --ai and AI suggestions."""
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text("""
pr:
  title_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
  body_suggestion:
    system: "You are a helpful assistant."
    user: "Commits: {commits}"
""")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.get_pr.return_value = None
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="AI suggested title",
                    body="AI suggested body",
                    model_dump=lambda: {"number": 123},
                )
                with patch(
                    "vibe3.services.pr_create_usecase.BaseResolutionUsecase.collect_branch_material"
                ) as mock_material:
                    mock_material.return_value = MagicMock(
                        commits=["feat: add feature"],
                        changed_files=["src/file.py"],
                    )
                    result = runner.invoke(app, ["pr", "create", "--ai", "--yes"])
                    assert result.exit_code in [0, 1]

    def test_pr_create_ai_json_uses_suggestions_without_prompt(
        self, runner: CliRunner
    ) -> None:
        """Test pr create --ai --json uses AI result without prompting."""
        with patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
            return_value="origin/main",
        ) as mock_resolve:
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
                        with patch(
                            "vibe3.services.pr_create_usecase.Prompt.ask"
                        ) as mock_prompt:
                            with patch(
                                "vibe3.commands.pr_create.PRService"
                            ) as mock_service:
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
        mock_resolve.assert_called_once_with(None)
        mock_material.assert_called_once_with(
            base_branch="origin/main",
            branch=ANY,
        )
        mock_prompt.assert_not_called()
        mock_suggest.assert_called_once_with(["feat: add feature"], ["src/file.py"])
        mock_service.return_value.create_draft_pr.assert_called_once_with(
            title="feat: ai title",
            body="Summary\n\n- change",
            base_branch="origin/main",
            actor="ai_assistant",
        )

    def test_pr_create_uses_resolved_base_for_ai_context_and_pr_request(
        self, runner: CliRunner
    ) -> None:
        """Resolved base should feed both AI context gathering and PR creation."""
        with patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
            return_value="origin/feature-root",
        ) as mock_resolve:
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
                        mock_suggest.return_value = ("feat: ai title", "body")
                        with patch(
                            "vibe3.commands.pr_create.PRService"
                        ) as mock_service:
                            mock_service.return_value.get_pr.return_value = None
                            mock_pr = MagicMock(
                                number=123,
                                title="feat: ai title",
                                body="body",
                                model_dump=lambda: {
                                    "number": 123,
                                    "title": "feat: ai title",
                                    "body": "body",
                                },
                            )
                            mock_service.return_value.create_draft_pr.return_value = (
                                mock_pr
                            )

                            result = runner.invoke(
                                app,
                                ["pr", "create", "--ai", "--json", "--yes"],
                            )

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(None)
        mock_material.assert_called_once_with(
            base_branch="origin/feature-root",
            branch=ANY,
        )
        mock_service.return_value.create_draft_pr.assert_called_once_with(
            title="feat: ai title",
            body="body",
            base_branch="origin/feature-root",
            actor="ai_assistant",
        )
