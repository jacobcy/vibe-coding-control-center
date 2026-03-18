"""GitClient 单元测试."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import GitError
from vibe3.models.change_source import (
    BranchSource,
    CommitSource,
    PRSource,
    UncommittedSource,
)

BRANCH = "feature/test"
SHA = "abc1234"


class TestGetCurrentBranch:
    """get_current_branch 测试."""

    def test_returns_branch_name(self) -> None:
        client = GitClient()
        with patch.object(client, "_run", return_value=BRANCH):
            assert client.get_current_branch() == BRANCH

    def test_raises_git_error_on_failure(self) -> None:
        client = GitClient()
        with patch.object(
            client, "_run", side_effect=GitError("rev-parse", "not a repo")
        ):
            with pytest.raises(GitError):
                client.get_current_branch()


class TestGetChangedFiles:
    """get_changed_files 统一接口测试."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_uncommitted_merges_staged_and_unstaged(self, client: GitClient) -> None:
        with patch.object(client, "_run", side_effect=["a.py\nb.py", "c.py"]):
            files = client.get_changed_files(UncommittedSource())
        assert sorted(files) == ["a.py", "b.py", "c.py"]

    def test_uncommitted_deduplicates(self, client: GitClient) -> None:
        with patch.object(client, "_run", side_effect=["a.py", "a.py"]):
            files = client.get_changed_files(UncommittedSource())
        assert files == ["a.py"]

    def test_commit_source(self, client: GitClient) -> None:
        with patch.object(client, "_run", return_value="x.py\ny.py"):
            files = client.get_changed_files(CommitSource(sha=SHA))
        assert "x.py" in files

    def test_branch_source(self, client: GitClient) -> None:
        with patch.object(client, "_run", return_value="z.py"):
            files = client.get_changed_files(BranchSource(branch=BRANCH, base="main"))
        assert files == ["z.py"]

    def test_pr_source_calls_gh_cli(self, client: GitClient) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "pr_file.py\n"
        with patch("subprocess.run", return_value=mock_result):
            files = client.get_changed_files(PRSource(pr_number=42))
        assert "pr_file.py" in files

    def test_pr_source_raises_on_gh_failure(self, client: GitClient) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "gh", stderr=b"not found"),
        ):
            with pytest.raises(GitError):
                client.get_changed_files(PRSource(pr_number=99))


class TestGetDiff:
    """get_diff 统一接口测试."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_uncommitted_diff(self, client: GitClient) -> None:
        with patch.object(client, "_run", return_value="diff content"):
            diff = client.get_diff(UncommittedSource())
        assert diff == "diff content"

    def test_commit_diff(self, client: GitClient) -> None:
        with patch.object(client, "_run", return_value="commit diff"):
            diff = client.get_diff(CommitSource(sha=SHA))
        assert diff == "commit diff"

    def test_branch_diff(self, client: GitClient) -> None:
        with patch.object(client, "_run", return_value="branch diff"):
            diff = client.get_diff(BranchSource(branch=BRANCH))
        assert diff == "branch diff"
