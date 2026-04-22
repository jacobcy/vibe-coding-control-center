"""Tests for CheckService.auto_fix_branch method."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check_service import CheckService


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    client._run.return_value = "/path/to/.git"
    return client


@pytest.fixture
def mock_github_client():
    """Create a mock GitHubClient."""
    return MagicMock(spec=GitHubClient)


@pytest.fixture
def check_service(mock_store, mock_git_client, mock_github_client):
    """Create a CheckService instance with mocked dependencies."""
    return CheckService(
        store=mock_store,
        git_client=mock_git_client,
        github_client=mock_github_client,
    )


class TestAutoFixBranch:
    """Tests for auto_fix_branch method."""

    def test_auto_fix_branch_creates_handoff(self, check_service, mock_git_client):
        """auto_fix creates handoff for the specified branch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()

            with patch.object(
                check_service.git_client,
                "get_git_common_dir",
                return_value=str(git_dir),
            ):
                result = check_service.auto_fix(
                    ["Shared handoff file not found: /some/path/current.md"],
                    branch="feature/other-branch",
                )

        assert result.success

    def test_auto_fix_branch_unknown_issue_is_unfixable(
        self, check_service, mock_github_client
    ):
        """auto_fix_branch reports failure for unrecognised issue strings."""
        # "database missing pr_number" is no longer emitted by _check_branch
        # (GitHub-as-truth: PR state is fetched live, not cached locally).
        # Passing it to auto_fix should return success=False cleanly.
        result = check_service.auto_fix(
            ["Branch has open PR #789 but database missing pr_number"],
            branch="feature/other-branch",
        )
        assert not result.success
        mock_github_client.list_prs_for_branch.assert_not_called()
