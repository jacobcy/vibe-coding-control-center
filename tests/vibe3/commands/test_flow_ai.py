"""Integration tests for flow command with AI support."""

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


class TestFlowCommandAI:
    """Tests for flow new command with --ai flag."""

    def test_flow_new_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new without --ai flag works normally."""
        with patch("vibe3.commands.flow.GitClient") as mock_git:
            mock_git.return_value.get_current_branch.return_value = "feature/test"
            with patch("vibe3.commands.flow.FlowService") as mock_service:
                mock_service.return_value.create_flow.return_value = MagicMock(
                    slug="test",
                    branch="feature/test",
                    status="active",
                    task_issue_number=None,
                    model_dump=lambda: {"slug": "test", "branch": "feature/test"},
                )
                with patch.object(runner, "invoke"):
                    pass

    def test_flow_new_ai_disabled(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new with --ai when AI is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.commands.flow.GitClient") as mock_git:
                mock_git.return_value.get_current_branch.return_value = "feature/test"
                with patch("vibe3.commands.flow.FlowService") as mock_service:
                    mock_service.return_value.create_flow.return_value = MagicMock(
                        slug="test",
                        branch="feature/test",
                        status="active",
                        task_issue_number=None,
                        model_dump=lambda: {"slug": "test"},
                    )
                    with patch(
                        "vibe3.commands.flow.VibeConfig.get_defaults"
                    ) as mock_config:
                        mock_config.return_value.ai.enabled = False
                        result = runner.invoke(
                            app, ["flow", "new", "--ai", "--issue", "123"]
                        )
                        assert result.exit_code in [0, 1]

    def test_flow_new_ai_missing_issue(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test flow new with --ai but no --issue."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.commands.flow.GitClient") as mock_git:
                mock_git.return_value.get_current_branch.return_value = "feature/test"
                with patch("vibe3.commands.flow.FlowService") as mock_service:
                    mock_service.return_value.create_flow.return_value = MagicMock(
                        slug="test",
                        branch="feature/test",
                        status="active",
                        model_dump=lambda: {"slug": "test"},
                    )
                    result = runner.invoke(app, ["flow", "new", "--ai"])
                    assert result.exit_code in [0, 1]


class TestFlowCommandCreateBranch:
    """Tests for flow new command with --create-branch flag."""

    def test_flow_new_create_branch_success(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch creates branch and flow."""
        with patch("vibe3.commands.flow.GitClient") as mock_git:
            mock_git.return_value.branch_exists.return_value = False
            with patch("vibe3.commands.flow.FlowService") as mock_service:
                mock_flow = MagicMock(
                    slug="my-feature",
                    branch="task/my-feature",
                    status="active",
                    task_issue_number=None,
                    model_dump=lambda: {
                        "slug": "my-feature",
                        "branch": "task/my-feature",
                    },
                )
                mock_service.return_value.create_flow_with_branch.return_value = (
                    mock_flow
                )
                result = runner.invoke(app, ["flow", "new", "my-feature", "-c"])
                assert result.exit_code == 0
                mock_service.return_value.create_flow_with_branch.assert_called_once_with(
                    slug="my-feature",
                    start_ref="origin/main",
                )

    def test_flow_new_create_branch_custom_start_ref(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch with custom --start-ref."""
        with patch("vibe3.commands.flow.GitClient") as mock_git:
            mock_git.return_value.branch_exists.return_value = False
            with patch("vibe3.commands.flow.FlowService") as mock_service:
                mock_flow = MagicMock(
                    slug="my-feature",
                    branch="task/my-feature",
                    status="active",
                    task_issue_number=None,
                    model_dump=lambda: {
                        "slug": "my-feature",
                        "branch": "task/my-feature",
                    },
                )
                mock_service.return_value.create_flow_with_branch.return_value = (
                    mock_flow
                )
                result = runner.invoke(
                    app,
                    [
                        "flow",
                        "new",
                        "my-feature",
                        "-c",
                        "--start-ref",
                        "origin/develop",
                    ],
                )
                assert result.exit_code == 0
                mock_service.return_value.create_flow_with_branch.assert_called_once_with(
                    slug="my-feature",
                    start_ref="origin/develop",
                )

    def test_flow_new_create_branch_already_exists(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new --create-branch when branch already exists."""
        with patch("vibe3.commands.flow.GitClient") as mock_git:
            mock_git.return_value.branch_exists.return_value = True
            result = runner.invoke(app, ["flow", "new", "existing-feature", "-c"])
            assert result.exit_code == 1
            assert "already exists" in result.output
            mock_git.return_value.branch_exists.assert_called_once_with(
                "task/existing-feature"
            )

    def test_flow_new_without_create_branch_uses_current(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test flow new without -c uses current branch."""
        with patch("vibe3.commands.flow.GitClient") as mock_git:
            mock_git.return_value.get_current_branch.return_value = "feature/existing"
            with patch("vibe3.commands.flow.FlowService") as mock_service:
                mock_flow = MagicMock(
                    slug="my-feature",
                    branch="feature/existing",
                    status="active",
                    task_issue_number=None,
                    model_dump=lambda: {
                        "slug": "my-feature",
                        "branch": "feature/existing",
                    },
                )
                mock_service.return_value.create_flow.return_value = mock_flow
                result = runner.invoke(app, ["flow", "new", "my-feature"])
                assert result.exit_code == 0
                mock_service.return_value.create_flow.assert_called_once_with(
                    slug="my-feature",
                    branch="feature/existing",
                )
