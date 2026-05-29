"""Tests for branch_compare utilities."""

from unittest.mock import MagicMock

from vibe3.utils.branch_compare import (
    BranchBehindInfo,
    check_branch_behind,
    format_branch_behind_body,
    format_branch_behind_console,
)


class TestCheckBranchBehind:
    """Tests for check_branch_behind function."""

    def test_up_to_date_returns_none(self) -> None:
        """When branch is up-to-date, return None."""
        mock_git = MagicMock()
        mock_git._run.return_value = "0"

        result = check_branch_behind(mock_git, "feature", "main")

        assert result is None
        mock_git._run.assert_called()

    def test_behind_n_commits_returns_info(self) -> None:
        """When branch is behind N commits, return BranchBehindInfo with count."""
        mock_git = MagicMock()
        # First call for fetch, second for rev-list
        mock_git._run.side_effect = ["", "5"]

        result = check_branch_behind(mock_git, "feature", "main")

        assert result is not None
        assert isinstance(result, BranchBehindInfo)
        assert result.head_branch == "feature"
        assert result.base_branch == "main"
        assert result.behind_count == 5

    def test_origin_head_not_exists_returns_none(self) -> None:
        """When origin/{head} doesn't exist, return None (git error)."""
        from vibe3.exceptions import GitError

        mock_git = MagicMock()
        # First call (fetch) succeeds, second call (rev-list) fails
        mock_git._run.side_effect = [
            "",  # fetch succeeds
            GitError("rev-list", "fatal: bad revision"),  # rev-list fails
        ]

        result = check_branch_behind(mock_git, "nonexistent", "main")

        assert result is None

    def test_fetch_failure_continues_with_warning(self) -> None:
        """When fetch fails, continue with stale refs (log warning)."""
        from vibe3.exceptions import GitError

        mock_git = MagicMock()
        # First call (fetch) fails, second call (rev-list) succeeds
        mock_git._run.side_effect = [
            GitError("fetch", "network error"),
            "3",
        ]

        result = check_branch_behind(mock_git, "feature", "main")

        assert result is not None
        assert result.behind_count == 3

    def test_invalid_output_returns_none(self) -> None:
        """When git rev-list returns invalid output, return None."""
        mock_git = MagicMock()
        # First call (fetch) succeeds, second call (rev-list) returns invalid output
        mock_git._run.side_effect = [
            "",  # fetch succeeds
            "not-a-number",  # rev-list returns invalid output
        ]

        result = check_branch_behind(mock_git, "feature", "main")

        assert result is None


class TestFormatBranchBehindBody:
    """Tests for format_branch_behind_body function."""

    def test_output_contains_branch_names(self) -> None:
        """Output should contain head and base branch names."""
        info = BranchBehindInfo(
            head_branch="feature-branch",
            base_branch="main",
            behind_count=5,
        )

        result = format_branch_behind_body(info)

        assert "feature-branch" in result
        assert "main" in result
        assert "5" in result

    def test_output_is_markdown(self) -> None:
        """Output should be formatted as markdown."""
        info = BranchBehindInfo(
            head_branch="feature",
            base_branch="main",
            behind_count=3,
        )

        result = format_branch_behind_body(info)

        assert "## ⚠️" in result
        assert "```bash" in result
        assert "git fetch" in result
        assert "git rebase" in result

    def test_output_contains_recommended_actions(self) -> None:
        """Output should contain recommended git commands."""
        info = BranchBehindInfo(
            head_branch="feature",
            base_branch="main",
            behind_count=10,
        )

        result = format_branch_behind_body(info)

        assert "git fetch origin main" in result
        assert "git rebase origin/main" in result
        assert "git push --force-with-lease" in result


class TestFormatBranchBehindConsole:
    """Tests for format_branch_behind_console function."""

    def test_output_contains_branch_names(self) -> None:
        """Output should contain head and base branch names."""
        info = BranchBehindInfo(
            head_branch="feature-branch",
            base_branch="main",
            behind_count=5,
        )

        result = format_branch_behind_console(info)

        assert "feature-branch" in result
        assert "main" in result
        assert "5" in result

    def test_output_is_rich_markup(self) -> None:
        """Output should contain Rich markup tags."""
        info = BranchBehindInfo(
            head_branch="feature",
            base_branch="main",
            behind_count=3,
        )

        result = format_branch_behind_console(info)

        assert "[bold red]" in result
        assert "[yellow]" in result
        assert "[cyan]" in result

    def test_output_contains_recommended_actions(self) -> None:
        """Output should contain recommended git commands."""
        info = BranchBehindInfo(
            head_branch="feature",
            base_branch="main",
            behind_count=10,
        )

        result = format_branch_behind_console(info)

        assert "git fetch origin main" in result
        assert "git rebase origin/main" in result
        assert "git push --force-with-lease" in result
