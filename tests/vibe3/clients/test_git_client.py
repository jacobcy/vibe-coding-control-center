"""GitClient 单元测试."""

import os
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.git_client import GitClient, find_repo_root
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


class TestGetRemoteUrl:
    """get_remote_url 测试."""

    def test_returns_remote_url_on_success(self) -> None:
        client = GitClient()
        url = "https://github.com/user/repo.git"
        with patch.object(client, "_run", return_value=url) as mock_run:
            assert client.get_remote_url() == url

        mock_run.assert_called_once_with(["remote", "get-url", "origin"])

    def test_returns_none_on_no_remote(self) -> None:
        client = GitClient()
        with patch.object(
            client, "_run", side_effect=GitError("remote get-url", "no such remote")
        ):
            assert client.get_remote_url() is None

    def test_passes_remote_name(self) -> None:
        client = GitClient()
        url = "https://github.com/user/upstream.git"
        with patch.object(client, "_run", return_value=url) as mock_run:
            assert client.get_remote_url(name="upstream") == url

        mock_run.assert_called_once_with(["remote", "get-url", "upstream"])


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
            env=mock.ANY,
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


class TestFindRepoRoot:
    """Tests for the shared repo-root resolution function."""

    def test_client_method_uses_instance_cwd(self, tmp_path: Path) -> None:
        """An injected client's cwd, not the process cwd, selects the repository."""
        other_repo = tmp_path / "other"
        other_repo.mkdir()
        env = dict(os.environ)
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_PREFIX", "GIT_COMMON_DIR"):
            env.pop(key, None)
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=other_repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        assert GitClient(cwd=other_repo).find_repo_root() == other_repo

    def test_git_common_dir_success(self):
        """Primary path: git common dir resolves to main repo."""
        with patch(
            "vibe3.utils.git_helpers.get_git_common_dir",
            return_value="/repos/main/.git",
        ):
            root = find_repo_root()
        assert root == Path("/repos/main")

    def test_worktree_git_file_absolute_gitdir(self):
        """Fallback: absolute gitdir in .git file from worktree."""
        git_common_fail = GitError("rev-parse", "failed")
        with (
            patch(
                "vibe3.utils.git_helpers.get_git_common_dir",
                side_effect=git_common_fail,
            ),
            patch.object(Path, "cwd", return_value=Path("/worktrees/wt-dev")),
            patch.object(Path, "is_file", return_value=True),
            patch.object(
                Path,
                "read_text",
                return_value="gitdir: /repos/main/.git/worktrees/wt-dev\n",
            ),
            patch(
                "vibe3.utils.git_helpers.resolve_repo_root_from_common_dir",
                return_value=Path("/repos/main"),
            ) as resolve_root,
        ):
            root = find_repo_root()
        assert root == Path("/repos/main")
        resolve_root.assert_called_once_with(
            Path("/repos/main/.git"), cwd=Path("/worktrees/wt-dev")
        )

    def test_worktree_git_file_relative_gitdir(self):
        """Fallback: relative gitdir resolved against cwd."""
        git_common_fail = GitError("rev-parse", "failed")
        with (
            patch(
                "vibe3.utils.git_helpers.get_git_common_dir",
                side_effect=git_common_fail,
            ),
            patch.object(Path, "cwd", return_value=Path("/worktrees/wt-dev")),
            patch.object(Path, "is_file", return_value=True),
            patch.object(
                Path,
                "read_text",
                return_value="gitdir: ../.git/worktrees/wt-dev\n",
            ),
            patch(
                "vibe3.utils.git_helpers.resolve_repo_root_from_common_dir",
                return_value=Path("/worktrees"),
            ) as resolve_root,
        ):
            root = find_repo_root()
        # ../.git/worktrees/wt-dev → /worktrees/.git/worktrees/wt-dev
        # parent.parent.parent → /worktrees
        assert root == Path("/worktrees")
        resolve_root.assert_called_once_with(
            Path("/worktrees/.git"), cwd=Path("/worktrees/wt-dev")
        )

    def test_main_repo_returns_cwd(self):
        """When .git is a directory, cwd IS the main repo."""
        git_common_fail = GitError("rev-parse", "failed")
        with (
            patch(
                "vibe3.utils.git_helpers.get_git_common_dir",
                side_effect=git_common_fail,
            ),
            patch.object(Path, "cwd", return_value=Path("/repos/main")),
            patch.object(Path, "is_file", return_value=False),
            patch.object(Path, "is_dir", return_value=True),
        ):
            root = find_repo_root()
        assert root == Path("/repos/main")

    def test_not_in_git_repo_raises(self):
        """Not in a git repo should raise SystemError."""
        git_common_fail = GitError("rev-parse", "failed")
        with (
            patch(
                "vibe3.utils.git_helpers.get_git_common_dir",
                side_effect=git_common_fail,
            ),
            patch.object(Path, "cwd", return_value=Path("/some/random/dir")),
            patch.object(Path, "is_file", return_value=False),
            patch.object(Path, "is_dir", return_value=False),
        ):
            with pytest.raises(SystemError, match="Cannot resolve repository root"):
                find_repo_root()


def test_pack_refs_all_calls_git_pack_refs(monkeypatch):
    """pack_refs_all should invoke git pack-refs --all."""
    from vibe3.clients import GitClient

    captured = {}

    def mock_run(self, args, **kwargs):
        captured["args"] = args
        return ""

    monkeypatch.setattr(GitClient, "_run", mock_run)
    GitClient().pack_refs_all()
    assert captured["args"] == ["pack-refs", "--all"]


class TestResolveBaseRef:
    """_resolve_base_ref 测试."""

    @pytest.fixture(autouse=True)
    def _clear_fetch_cache(self) -> Generator[None, None, None]:
        """Clear module-level fetch cache before each test."""
        from vibe3.clients.git_client import _fetch_cache

        _fetch_cache.clear()
        yield
        _fetch_cache.clear()

    def test_remote_qualified_ref_unchanged(self) -> None:
        """Already qualified remote ref is returned unchanged."""
        client = GitClient()
        result = client._resolve_base_ref("origin/main")
        assert result == "origin/main"

    def test_local_ref_resolved_to_remote(self) -> None:
        """Local 'main' is resolved to 'origin/main' with fetch."""
        client = GitClient()
        with patch.object(client, "fetch") as mock_fetch:
            result = client._resolve_base_ref("main")

        assert result == "origin/main"
        mock_fetch.assert_called_once_with("origin", "main")

    def test_cache_hit_within_ttl(self) -> None:
        """Second call within TTL uses cache and skips fetch."""
        client = GitClient()
        with patch.object(client, "fetch") as mock_fetch:
            client._resolve_base_ref("main")
            assert mock_fetch.call_count == 1

            # Second call with same base — should use cache
            client._resolve_base_ref("main")
            assert mock_fetch.call_count == 1  # No additional fetch

    def test_cache_expired_refetches(self) -> None:
        """After TTL expiry, cache is bypassed and refetch occurs."""
        from vibe3.clients.git_client import _fetch_cache

        client = GitClient()
        with patch.object(client, "fetch") as mock_fetch:
            client._resolve_base_ref("main")
            assert mock_fetch.call_count == 1

            # Advance time past TTL (300s) by manually tweaking cache entry
            cache_key = "fetch:origin/main"
            _fetch_cache[cache_key] = time.time() - 301  # Past TTL

            client._resolve_base_ref("main")
            assert mock_fetch.call_count == 2  # Refetched

    def test_fetch_failure_returns_remote_ref(self) -> None:
        """When fetch fails, _resolve_base_ref still returns remote ref."""
        client = GitClient()
        with patch.object(client, "fetch", side_effect=GitError("fetch", "failed")):
            result = client._resolve_base_ref("main")

        assert result == "origin/main"


class TestResolveSource:
    """_resolve_source 测试."""

    def test_branch_source_base_resolved(self) -> None:
        """BranchSource base is resolved to remote ref."""
        client = GitClient()
        with patch.object(client, "fetch"):
            source = BranchSource(branch="feature/x", base="main")
            resolved = client._resolve_source(source)

        assert isinstance(resolved, BranchSource)
        assert resolved.base == "origin/main"
        assert resolved.branch == "feature/x"

    def test_non_branch_source_returned_unchanged(self) -> None:
        """Non-BranchSource (CommitSource, PRSource, UncommittedSource) not resolved."""
        client = GitClient()

        # CommitSource
        cs = CommitSource(sha="abc123")
        assert client._resolve_source(cs) is cs

        # PRSource
        mock_gh = MagicMock()
        client_with_gh = GitClient(github_client=mock_gh)
        ps = PRSource(pr_number=42)
        assert client_with_gh._resolve_source(ps) is ps

        # UncommittedSource
        us = UncommittedSource()
        assert client._resolve_source(us) is us


class TestFetchRefspecConstruction:
    """Verify fetch() constructs correct refspecs after PR #3246 fix."""

    def test_fetch_bare_branch_adds_refspec(self):
        """fetch('origin', 'main') constructs 'main:refs/remotes/origin/main'."""
        client = GitClient()
        captured_args = []

        def fake_run(args, cwd=None):
            if args[0] == "fetch":
                captured_args.append(args[:])

        with patch.object(client, "_run", side_effect=fake_run):
            client.fetch("origin", "main")

        assert len(captured_args) == 1
        fetch_args = captured_args[0]
        assert "main:refs/remotes/origin/main" in fetch_args

    def test_fetch_full_ref_passed_through(self):
        """fetch('origin', 'refs/tags/v1') is passed through unchanged."""
        client = GitClient()
        captured_args = []

        def fake_run(args, cwd=None):
            if args[0] == "fetch":
                captured_args.append(args[:])

        with patch.object(client, "_run", side_effect=fake_run):
            client.fetch("origin", "refs/tags/v1")

        assert len(captured_args) == 1
        fetch_args = captured_args[0]
        assert "refs/tags/v1" in fetch_args

    def test_fetch_refspec_with_colon_passed_through(self):
        """fetch('origin', 'a:b') passes through unchanged."""
        client = GitClient()
        captured_args = []

        def fake_run(args, cwd=None):
            if args[0] == "fetch":
                captured_args.append(args[:])

        with patch.object(client, "_run", side_effect=fake_run):
            client.fetch("origin", "a:b")

        assert len(captured_args) == 1
        fetch_args = captured_args[0]
        assert "a:b" in fetch_args
