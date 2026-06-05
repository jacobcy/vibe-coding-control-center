"""Tests for GitHub client base functionality."""

import subprocess
from unittest.mock import MagicMock, patch

from vibe3.clients.github_client_base import GH_API_TIMEOUT, GitHubClientBase


class TestRunGhCommand:
    """Tests for _run_gh_command helper method."""

    def test_successful_command_execution(self) -> None:
        """Test successful command execution returns CompletedProcess."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="success output",
                stderr="",
            )

            result = client._run_gh_command(["gh", "issue", "list"])

            assert result is not None
            assert result.returncode == 0
            assert result.stdout == "success output"
            mock_run.assert_called_once()

    def test_timeout_returns_none_and_logs_warning(self) -> None:
        """Test TimeoutExpired returns None and logs warning."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh"], timeout=30)

            result = client._run_gh_command(["gh", "issue", "list"])

            assert result is None
            mock_run.assert_called_once()

    def test_filenotfound_returns_none_and_logs_warning(self) -> None:
        """Test FileNotFoundError returns None and logs warning."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = client._run_gh_command(["gh", "issue", "list"])

            assert result is None
            mock_run.assert_called_once()

    def test_pager_true_injects_gh_pager_env(self) -> None:
        """Test pager=True injects GH_PAGER=cat into env."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = client._run_gh_command(["gh", "issue", "view", "123"], pager=True)

            assert result is not None
            # Verify that env was passed with GH_PAGER=cat
            call_kwargs = mock_run.call_args[1]
            assert "env" in call_kwargs
            assert call_kwargs["env"]["GH_PAGER"] == "cat"

    def test_pager_false_does_not_inject_env(self) -> None:
        """Test pager=False does not inject env."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = client._run_gh_command(["gh", "issue", "list"], pager=False)

            assert result is not None
            # Verify that env was not passed
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("env") is None

    def test_timeout_parameter_overrides_default(self) -> None:
        """Test timeout parameter overrides GH_API_TIMEOUT default."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = client._run_gh_command(["gh", "issue", "list"], timeout=60)

            assert result is not None
            # Verify that timeout was passed as 60
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 60

    def test_default_timeout_uses_gh_api_timeout(self) -> None:
        """Test default timeout uses GH_API_TIMEOUT."""
        client = GitHubClientBase()

        with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = client._run_gh_command(["gh", "issue", "list"])

            assert result is not None
            # Verify that timeout was passed as GH_API_TIMEOUT
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == GH_API_TIMEOUT
