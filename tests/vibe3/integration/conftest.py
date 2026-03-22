"""Shared fixtures for integration tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_all_dependencies():
    """Mock all external dependencies for PR analysis."""
    with (
        patch("vibe3.commands.inspect_pr_helpers._get_pr_changed_files") as mock_files,
        patch(
            "vibe3.commands.inspect_pr_helpers._filter_critical_files"
        ) as mock_filter,
        patch(
            "vibe3.commands.inspect_pr_helpers._analyze_critical_files"
        ) as mock_analyze,
        patch("vibe3.commands.inspect_pr_helpers._calculate_risk_score") as mock_score,
        patch("vibe3.commands.inspect_pr_helpers._get_recent_commits") as mock_commits,
        patch("vibe3.commands.inspect_pr_helpers._get_pr_commit_count") as mock_count,
        patch("vibe3.commands.inspect_pr_helpers.dag_service") as mock_dag,
        patch("vibe3.clients.git_client.GitClient") as mock_git_client_class,
    ):
        # Setup default returns
        mock_files.return_value = [
            "src/vibe3/config/settings.py",
            "src/vibe3/utils/helpers.py",
            "tests/test_foo.py",
        ]

        mock_filter.return_value = [
            {
                "path": "src/vibe3/config/settings.py",
                "critical_path": True,
                "public_api": False,
            }
        ]

        mock_analyze.return_value = (
            {"src/vibe3/config/settings.py": ["get_config", "ConfigPaths"]},
            {"src/vibe3/config/settings.py": ["vibe3.config", "vibe3.utils"]},
        )

        mock_dag_result = MagicMock()
        mock_dag_result.impacted_modules = ["vibe3.config", "vibe3.utils"]
        mock_dag.expand_impacted_modules.return_value = mock_dag_result

        mock_score.return_value = {
            "score": 6,
            "level": "MEDIUM",
            "block": False,
        }

        mock_commits.return_value = [
            {"sha": "abc1234", "message": "Add feature"},
            {"sha": "def5678", "message": "Fix bug"},
        ]

        mock_count.return_value = 5

        # Mock GitClient.get_diff to avoid GitHub API calls
        mock_git_client = MagicMock()
        mock_git_client.get_diff.return_value = "+line1\n-line2\n+line3"
        mock_git_client_class.return_value = mock_git_client

        yield {
            "files": mock_files,
            "filter": mock_filter,
            "analyze": mock_analyze,
            "score": mock_score,
            "commits": mock_commits,
            "count": mock_count,
            "dag": mock_dag,
            "git_client": mock_git_client,
        }