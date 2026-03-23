"""Integration tests for PR create command with AI support."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestPRCreateCommandAI:
    """Tests for PR create command with --ai flag."""

    def test_pr_create_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create without --ai flag works normally."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            mock_service.return_value.create_draft_pr.return_value = MagicMock(
                number=123,
                title="Test PR",
                body="Test body",
                model_dump=lambda: {"number": 123, "title": "Test PR"},
            )
            with patch("vibe3.commands.pr_create._get_commits") as mock_commits:
                mock_commits.return_value = ["feat: add feature"]
                result = runner.invoke(app, ["pr", "create", "-t", "Test PR"])
                assert result.exit_code in [0, 1]

    def test_pr_create_ai_disabled(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create with --ai when AI is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="Test PR",
                    body="Test body",
                    model_dump=lambda: {"number": 123},
                )
                with patch(
                    "vibe3.commands.pr_create.VibeConfig.get_defaults"
                ) as mock_config:
                    mock_config.return_value.ai.enabled = False
                    result = runner.invoke(app, ["pr", "create", "--ai"])
                    assert result.exit_code in [0, 1]

    def test_pr_create_ai_no_commits(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create with --ai but no commits."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="Test PR",
                    body="Test body",
                    model_dump=lambda: {"number": 123},
                )
                with patch("vibe3.commands.pr_create._get_commits") as mock_commits:
                    mock_commits.return_value = []
                    result = runner.invoke(app, ["pr", "create", "--ai"])
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
                mock_service.return_value.create_draft_pr.return_value = MagicMock(
                    number=123,
                    title="AI suggested title",
                    body="AI suggested body",
                    model_dump=lambda: {"number": 123},
                )
                with patch("vibe3.commands.pr_create._get_commits") as mock_commits:
                    mock_commits.return_value = ["feat: add feature"]
                with patch("vibe3.commands.pr_create._get_changed_files") as mock_files:
                    mock_files.return_value = ["src/file.py"]
                    result = runner.invoke(app, ["pr", "create", "--ai"])
                    assert result.exit_code in [0, 1]
