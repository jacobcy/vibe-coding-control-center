"""Tests for CI parity - ensuring tests behave consistently across environments.

These tests verify that our test suite doesn't have hidden dependencies on:
- Specific working directory paths
- Specific git repository state
- Specific environment variables
"""

import os
from pathlib import Path


class TestWorkingDirectoryIndependence:
    """Verify tests don't depend on specific working directory."""

    def test_repo_root_detection_works_from_subdirectory(self) -> None:
        """Verify repo root detection works from any subdirectory."""
        import os

        from vibe3.services.path_helpers import get_worktree_root

        # Save current working directory
        original_cwd = os.getcwd()

        try:
            # Get the repo root first (while we're in a valid git directory)
            worktree_root = get_worktree_root()
            root_path = Path(worktree_root)

            # Create a subdirectory within the repo
            subdir = root_path / "src" / "vibe3" / "utils"
            if subdir.exists():
                # Change to subdirectory within the repo
                os.chdir(str(subdir))

                # Should work from any directory within the repo
                worktree_root_from_subdir = get_worktree_root()
                assert worktree_root_from_subdir == worktree_root
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def test_config_loading_independent_of_cwd(self) -> None:
        """Verify config loading works from any working directory."""
        import os

        from vibe3.config.loader import get_config
        from vibe3.services.path_helpers import get_worktree_root

        # Save current working directory
        original_cwd = os.getcwd()

        try:
            # Get the repo root and create a subdirectory within it
            worktree_root = get_worktree_root()
            root_path = Path(worktree_root)
            subdir = root_path / "src" / "vibe3" / "utils"

            if subdir.exists():
                # Change to subdirectory within the repo
                os.chdir(str(subdir))

                # This should work regardless of current working directory
                config = get_config()
                assert config is not None
        finally:
            # Restore original working directory
            os.chdir(original_cwd)


class TestGitStateIndependence:
    """Verify tests don't depend on specific git state."""

    def test_inspect_base_works_with_mocked_git(self) -> None:
        """Verify inspect base works with mocked git state."""
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from vibe3.commands.inspect import app

        runner = CliRunner()
        mock_git = MagicMock()
        mock_git.get_changed_files.return_value = []

        with patch("vibe3.clients.GitClient", return_value=mock_git):
            with patch(
                "vibe3.utils.git_helpers.get_current_branch", return_value="test-branch"
            ):
                with patch("vibe3.config.loader.get_config") as mock_config:
                    mock_config.return_value.review_scope.critical_paths = []
                    mock_config.return_value.review_scope.public_api_paths = []
                    with patch(
                        "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
                        return_value=MagicMock(base_branch="main"),
                    ):
                        result = runner.invoke(app, ["base"])

        assert result.exit_code == 0


class TestEnvironmentVariableIndependence:
    """Verify tests handle environment variables correctly."""

    def test_github_actions_env_not_required_for_tests(self) -> None:
        """Tests should pass regardless of GITHUB_ACTIONS env var."""
        # This test verifies our tests don't accidentally depend on CI env
        original = os.environ.get("GITHUB_ACTIONS")

        try:
            # Should work with GITHUB_ACTIONS unset
            os.environ.pop("GITHUB_ACTIONS", None)
            # If a test requires GITHUB_ACTIONS=true, it should mock it

            # Import and verify basic functionality works
            from vibe3.config.loader import get_config

            config = get_config()
            assert config is not None

        finally:
            if original is not None:
                os.environ["GITHUB_ACTIONS"] = original
