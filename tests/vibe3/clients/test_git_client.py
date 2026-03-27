"""GitClient 单元测试."""

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


class TestGitClientInit:
    """GitClient 初始化测试."""

    def test_init_without_github_client(self) -> None:
        """测试不注入 GitHubClient."""
        client = GitClient()
        assert client._github_client is None

    def test_init_with_github_client(self) -> None:
        """测试注入 GitHubClient."""
        mock_gh = MagicMock()
        client = GitClient(github_client=mock_gh)
        assert client._github_client is mock_gh


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


class TestGetCommitSubjects:
    """get_commit_subjects 测试."""

    def test_returns_commit_subjects_between_refs(self) -> None:
        client = GitClient()
        with patch.object(
            client,
            "_run",
            return_value="feat: base resolver\nrefactor: thin pr create",
        ) as mock_run:
            subjects = client.get_commit_subjects("origin/main", "task/demo")

        assert subjects == ["feat: base resolver", "refactor: thin pr create"]
        mock_run.assert_called_once_with(
            ["log", "origin/main..task/demo", "--oneline", "--format=%s"]
        )


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

    def test_pr_source_with_github_client(self, client: GitClient) -> None:
        """测试 PR source 使用注入的 GitHubClient."""
        mock_gh = MagicMock()
        mock_gh.get_pr_files.return_value = ["pr_file.py"]

        client_with_dep = GitClient(github_client=mock_gh)
        files = client_with_dep.get_changed_files(PRSource(pr_number=42))

        assert "pr_file.py" in files
        mock_gh.get_pr_files.assert_called_once_with(42)

    def test_pr_source_without_github_client_raises(self, client: GitClient) -> None:
        """测试 PR source 但未注入 GitHubClient 时抛出错误."""
        with pytest.raises(GitError, match="requires GitHubClient"):
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

    def test_pr_diff_with_github_client(self, client: GitClient) -> None:
        """测试 PR diff 使用注入的 GitHubClient."""
        mock_gh = MagicMock()
        mock_gh.get_pr_diff.return_value = "pr diff content"

        client_with_dep = GitClient(github_client=mock_gh)
        diff = client_with_dep.get_diff(PRSource(pr_number=42))

        assert diff == "pr diff content"
        mock_gh.get_pr_diff.assert_called_once_with(42)

    def test_pr_diff_without_github_client_raises(self, client: GitClient) -> None:
        """测试 PR diff 但未注入 GitHubClient 时抛出错误."""
        with pytest.raises(GitError, match="requires GitHubClient"):
            client.get_diff(PRSource(pr_number=99))
