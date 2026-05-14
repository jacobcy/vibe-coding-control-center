"""Tests for git status ops functions."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_status_ops import _numstat_via_merge_base, get_numstat
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
