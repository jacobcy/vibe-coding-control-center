"""Tests for git status ops functions."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_status_ops import (
    _filter_unified_diff_by_paths,
    _numstat_via_merge_base,
    get_changed_files,
    get_numstat,
)
from vibe3.exceptions import GitError, SystemError
from vibe3.models.change_source import (
    BranchSource,
    CommitSource,
    PRSource,
    UncommittedSource,
)


class TestGetNumstat:
    """Test get_numstat function."""

    def test_uncommitted_source_uses_head(self) -> None:
        """Test uncommitted source uses 'git diff --numstat HEAD'."""
        run = MagicMock(return_value="10\t5\tsrc/test.py")
        source = UncommittedSource()

        result = get_numstat(run, source)

        run.assert_called_once_with(["diff", "--numstat", "HEAD"])
        assert result == "10\t5\tsrc/test.py"

    def test_commit_source_uses_sha_range(self) -> None:
        """Test commit source uses 'git diff --numstat sha^ sha'."""
        run = MagicMock(return_value="15\t8\tsrc/main.py")
        source = CommitSource(sha="abc123")

        result = get_numstat(run, source)

        run.assert_called_once_with(["diff", "--numstat", "abc123^", "abc123"])
        assert result == "15\t8\tsrc/main.py"

    def test_branch_source_uses_merge_base(self) -> None:
        """Test branch source uses merge-base correctly."""
        run = MagicMock(return_value="20\t10\tsrc/feature.py")
        merge_base_sha = "a" * 40
        get_merge_base = MagicMock(return_value=merge_base_sha)
        source = BranchSource(branch="feature", base="main")

        result = get_numstat(run, source, get_merge_base=get_merge_base)

        get_merge_base.assert_called_once_with("feature", "main")
        expected_args = ["diff", "--numstat", f"{merge_base_sha}...feature"]
        run.assert_called_once_with(expected_args)
        assert result == "20\t10\tsrc/feature.py"

    def test_branch_source_raises_without_merge_base_callable(self) -> None:
        """Test branch source raises error when get_merge_base not provided."""
        run = MagicMock()
        source = BranchSource(branch="feature", base="main")

        with pytest.raises(SystemError, match="get_merge_base callable required"):
            get_numstat(run, source)

    def test_pr_source_uses_github_client(self) -> None:
        """Test PR source uses github_client.get_pr for ref resolution."""
        run = MagicMock(return_value="30\t15\tsrc/pr_file.py")
        github_client = MagicMock()
        pr_info = MagicMock()
        pr_info.head_branch = "pr-branch"
        pr_info.base_branch = "main"
        github_client.get_pr.return_value = pr_info
        merge_base_sha = "c" * 40
        get_merge_base = MagicMock(return_value=merge_base_sha)
        source = PRSource(pr_number=42)

        result = get_numstat(
            run, source, github_client=github_client, get_merge_base=get_merge_base
        )

        github_client.get_pr.assert_called_once_with(42)
        get_merge_base.assert_called_once_with("pr-branch", "main")
        expected_args = ["diff", "--numstat", f"{merge_base_sha}...pr-branch"]
        run.assert_called_once_with(expected_args)
        assert result == "30\t15\tsrc/pr_file.py"

    def test_pr_source_raises_without_github_client(self) -> None:
        """Test PR source raises error when github_client not provided."""
        run = MagicMock()
        get_merge_base = MagicMock()
        source = PRSource(pr_number=42)

        with pytest.raises(GitError, match="PR source requires GitHubClient"):
            get_numstat(run, source, get_merge_base=get_merge_base)

    def test_pr_source_raises_without_merge_base_callable(self) -> None:
        """Test PR source raises error when get_merge_base not provided."""
        run = MagicMock()
        github_client = MagicMock()
        source = PRSource(pr_number=42)

        with pytest.raises(SystemError, match="get_merge_base callable required"):
            get_numstat(run, source, github_client=github_client)

    def test_pr_source_raises_when_pr_not_found(self) -> None:
        """Test PR source raises error when get_pr returns None."""
        run = MagicMock()
        github_client = MagicMock()
        github_client.get_pr.return_value = None
        get_merge_base = MagicMock()
        source = PRSource(pr_number=999)

        with pytest.raises(GitError, match="PR #999 not found"):
            get_numstat(
                run, source, github_client=github_client, get_merge_base=get_merge_base
            )


class TestNumstatViaMergeBase:
    """Test _numstat_via_merge_base helper function."""

    def test_calls_merge_base_with_head_and_base(self) -> None:
        """Test that get_merge_base is called with (head, base) arguments."""
        run = MagicMock(return_value="5\t3\tsrc/file.py")
        get_merge_base = MagicMock(return_value="a" * 40)

        result = _numstat_via_merge_base(run, get_merge_base, "feature", "main")

        get_merge_base.assert_called_once_with("feature", "main")
        assert result == "5\t3\tsrc/file.py"

    def test_calls_run_with_correct_diff_args(self) -> None:
        """Test that run is called with correct diff --numstat arguments."""
        run = MagicMock(return_value="10\t2\tsrc/other.py")
        get_merge_base = MagicMock(return_value="b" * 40)

        result = _numstat_via_merge_base(run, get_merge_base, "branch", "main")

        run.assert_called_once_with(["diff", "--numstat", "b" * 40 + "...branch"])
        assert result == "10\t2\tsrc/other.py"

    def test_raises_on_empty_merge_base(self) -> None:
        """Test that empty merge_base raises SystemError."""
        run = MagicMock()
        get_merge_base = MagicMock(return_value="")
        with pytest.raises(SystemError, match="invalid SHA format"):
            _numstat_via_merge_base(run, get_merge_base, "feature", "main")

    def test_raises_on_wrong_length_merge_base(self) -> None:
        """Test that non-40-char merge_base raises SystemError."""
        run = MagicMock()
        get_merge_base = MagicMock(return_value="abc123")
        with pytest.raises(SystemError, match="invalid SHA format"):
            _numstat_via_merge_base(run, get_merge_base, "feature", "main")

    def test_raises_on_non_hex_merge_base(self) -> None:
        """Test that non-hex merge_base raises SystemError."""
        run = MagicMock()
        get_merge_base = MagicMock(return_value="ghij" + "0" * 36)
        with pytest.raises(SystemError, match="invalid SHA format"):
            _numstat_via_merge_base(run, get_merge_base, "feature", "main")


class TestGetChangedFilesPathspec:
    """Test get_changed_files pathspec parameter."""

    def test_uncommitted_source_passes_pathspec(self) -> None:
        """Test that pathspec is passed to git commands for uncommitted source."""
        run = MagicMock(side_effect=["", "", "file.py"])
        source = UncommittedSource()

        result = get_changed_files(run, source, pathspec="*.py")

        # Verify pathspec was added to all three git commands
        assert run.call_count == 3
        for call in run.call_args_list:
            assert call[0][0][-2:] == ["--", "*.py"]
        assert result == ["file.py"]

    def test_commit_source_passes_pathspec(self) -> None:
        """Test that pathspec is passed to git diff-tree for commit source."""
        run = MagicMock(return_value="src/main.py\nsrc/utils.py")
        source = CommitSource(sha="abc123")

        result = get_changed_files(run, source, pathspec="*.py")

        run.assert_called_once()
        args = run.call_args[0][0]
        assert args[:6] == [
            "diff-tree",
            "--no-commit-id",
            "-r",
            "--name-only",
            "-m",
            "abc123",
        ]
        assert args[-2:] == ["--", "*.py"]
        assert result == ["src/main.py", "src/utils.py"]

    def test_branch_source_passes_pathspec(self) -> None:
        """Test that pathspec is passed to git diff for branch source."""
        run = MagicMock(return_value="feature.py")
        source = BranchSource(branch="feature", base="main")

        result = get_changed_files(run, source, pathspec="*.py")

        run.assert_called_once_with(
            ["diff", "--name-only", "main...feature", "--", "*.py"]
        )
        assert result == ["feature.py"]

    def test_pr_source_filters_with_fnmatch(self) -> None:
        """Test that PR source uses fnmatch filtering for pathspec."""
        run = MagicMock()
        github_client = MagicMock()
        github_client.get_pr_files.return_value = [
            "src/main.py",
            "bin/script",
            "README.md",
        ]
        source = PRSource(pr_number=42)

        result = get_changed_files(
            run, source, github_client=github_client, pathspec="*.py"
        )

        github_client.get_pr_files.assert_called_once_with(42)
        assert result == ["src/main.py"]

    def test_pr_source_no_pathspec_returns_all(self) -> None:
        """Test that PR source returns all files when no pathspec."""
        run = MagicMock()
        github_client = MagicMock()
        github_client.get_pr_files.return_value = [
            "src/main.py",
            "bin/script",
            "README.md",
        ]
        source = PRSource(pr_number=42)

        result = get_changed_files(run, source, github_client=github_client)

        github_client.get_pr_files.assert_called_once_with(42)
        assert len(result) == 3


class TestFilterUnifiedDiffByPaths:
    """Test _filter_unified_diff_by_paths helper function."""

    def test_filters_matching_files_only(self) -> None:
        """Test that only files matching path prefixes are included."""
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1 +1 @@
-old
+new
diff --git a/docs/README.md b/docs/README.md
--- a/docs/README.md
+++ b/docs/README.md
@@ -1 +1 @@
-doc
+updated"""
        result = _filter_unified_diff_by_paths(diff, ["src/"])
        assert "src/main.py" in result
        assert "docs/README.md" not in result

    def test_handles_empty_diff(self) -> None:
        """Test that empty diff returns empty string."""
        assert _filter_unified_diff_by_paths("", ["src/"]) == ""

    def test_handles_multiple_path_prefixes(self) -> None:
        """Test filtering with multiple path prefixes."""
        diff = """diff --git a/src/a.py b/src/a.py
+a line
diff --git a/bin/b.sh b/bin/b.sh
+b line
diff --git a/lib/c.py b/lib/c.py
+c line"""
        result = _filter_unified_diff_by_paths(diff, ["src/", "bin/"])
        assert "src/a.py" in result
        assert "bin/b.sh" in result
        assert "lib/c.py" not in result

    def test_handles_path_without_trailing_slash(self) -> None:
        """Test that path prefix works without trailing slash."""
        diff = "diff --git a/src/main.py b/src/main.py\n+new line"
        result = _filter_unified_diff_by_paths(diff, ["src"])
        assert "src/main.py" in result
