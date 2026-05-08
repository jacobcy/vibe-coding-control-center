"""Tests for git status ops functions."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_status_ops import get_numstat
from vibe3.exceptions import GitError
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
        get_merge_base = MagicMock(return_value="base456")
        source = BranchSource(branch="feature", base="main")

        result = get_numstat(run, source, get_merge_base=get_merge_base)

        get_merge_base.assert_called_once_with("feature", "main")
        run.assert_called_once_with(["diff", "--numstat", "base456...feature"])
        assert result == "20\t10\tsrc/feature.py"

    def test_branch_source_raises_without_merge_base_callable(self) -> None:
        """Test branch source raises error when get_merge_base not provided."""
        run = MagicMock()
        source = BranchSource(branch="feature", base="main")

        with pytest.raises(ValueError, match="get_merge_base callable required"):
            get_numstat(run, source)

    def test_pr_source_uses_github_client(self) -> None:
        """Test PR source uses github_client.get_pr for ref resolution."""
        run = MagicMock(return_value="30\t15\tsrc/pr_file.py")
        github_client = MagicMock()
        pr_info = MagicMock()
        pr_info.head_branch = "pr-branch"
        pr_info.base_branch = "main"
        github_client.get_pr.return_value = pr_info
        get_merge_base = MagicMock(return_value="merge789")
        source = PRSource(pr_number=42)

        result = get_numstat(
            run, source, github_client=github_client, get_merge_base=get_merge_base
        )

        github_client.get_pr.assert_called_once_with(42)
        get_merge_base.assert_called_once_with("pr-branch", "main")
        run.assert_called_once_with(["diff", "--numstat", "merge789...pr-branch"])
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

        with pytest.raises(ValueError, match="get_merge_base callable required"):
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
