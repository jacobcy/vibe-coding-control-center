"""GitClient 单元测试."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.git_client import GitClient, clear_git_client_cache, get_git_client
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


class TestGetGitCommonDir:
    """get_git_common_dir 测试."""

    def test_returns_absolute_git_common_dir(self) -> None:
        client = GitClient()
        with patch.object(client, "_run", return_value="/repo/.git") as mock_run:
            assert client.get_git_common_dir() == "/repo/.git"

        mock_run.assert_called_once_with(
            ["rev-parse", "--path-format=absolute", "--git-common-dir"]
        )

    def test_raises_git_error_on_empty_git_common_dir(self) -> None:
        client = GitClient()
        with patch.object(client, "_run", return_value=""):
            with pytest.raises(GitError, match="returned empty path"):
                client.get_git_common_dir()

    def test_raises_git_error_on_relative_git_common_dir(self) -> None:
        client = GitClient()
        with patch.object(client, "_run", return_value=".git"):
            with pytest.raises(GitError, match="returned non-absolute path"):
                client.get_git_common_dir()


class TestListWorktrees:
    """list_worktrees 测试."""

    def test_parses_worktree_entries_with_cwd_override(self) -> None:
        porcelain_output = """worktree /tmp/main
branch refs/heads/main

worktree /tmp/do-20260430-abc123
branch refs/heads/task/issue-123
"""
        client = GitClient()

        with patch("vibe3.clients.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=porcelain_output)

            entries = client.list_worktrees(cwd=Path("/tmp/main"))

        assert entries == [
            ("/tmp/main", "refs/heads/main"),
            ("/tmp/do-20260430-abc123", "refs/heads/task/issue-123"),
        ]
        mock_run.assert_called_once_with(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd="/tmp/main",
        )


class TestGetChangedFiles:
    """get_changed_files 统一接口测试."""

    @pytest.fixture
    def client(self) -> GitClient:
        return GitClient()

    def test_uncommitted_merges_staged_and_unstaged(self, client: GitClient) -> None:
        with patch.object(client, "_run", side_effect=["a.py\nb.py", "c.py", "d.py"]):
            files = client.get_changed_files(UncommittedSource())
        assert sorted(files) == ["a.py", "b.py", "c.py", "d.py"]

    def test_uncommitted_deduplicates(self, client: GitClient) -> None:
        with patch.object(client, "_run", side_effect=["a.py", "a.py", ""]):
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


class TestCheckMergeConflicts:
    """check_merge_conflicts 测试."""

    def test_returns_false_when_abort_not_needed(self) -> None:
        """merge 成功但无 merge state 时，abort 失败也应视为无冲突."""
        client = GitClient()
        with patch.object(
            client,
            "_run",
            side_effect=[
                "",
                GitError("merge --abort", "There is no merge to abort"),
            ],
        ):
            assert client.check_merge_conflicts("origin/main") is False

    def test_returns_true_when_conflict_and_abort_fails(self) -> None:
        """merge 冲突且 abort 失败时，不应抛异常，应返回有冲突."""
        client = GitClient()
        with patch.object(
            client,
            "_run",
            side_effect=[
                GitError("merge", "CONFLICT"),
                GitError("merge --abort", "There is no merge to abort"),
            ],
        ):
            assert client.check_merge_conflicts("origin/main") is True


class TestGitClientFactory:
    """GitClient factory caching 测试."""

    def test_get_git_client_returns_cached_instance(self) -> None:
        """测试 get_git_client 返回缓存的实例."""
        clear_git_client_cache()

        client1 = get_git_client()
        client2 = get_git_client()

        assert client1 is client2

    def test_clear_git_client_cache_clears_cache(self) -> None:
        """测试 clear_git_client_cache 清除缓存."""
        clear_git_client_cache()

        client1 = get_git_client()
        clear_git_client_cache()
        client2 = get_git_client()

        assert client1 is not client2

    def test_factory_does_not_interfere_with_direct_instantiation(self) -> None:
        """测试工厂方法不干扰直接实例化."""
        clear_git_client_cache()

        factory_client = get_git_client()
        direct_client = GitClient()

        assert factory_client is not direct_client
