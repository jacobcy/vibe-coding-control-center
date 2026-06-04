"""Unit tests for find_parent_branch performance optimization."""

from unittest.mock import patch

from vibe3.utils.branch_utils import find_parent_branch


class TestFindParentBranch:
    """Tests for find_parent_branch function."""

    def test_find_parent_main_branch(self) -> None:
        """Test finding parent when on main branch (root branch with no parent)."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            # Mock getting current branch and walking commits
            mock_git.side_effect = [
                "main",  # rev-parse --abbrev-ref HEAD
                "abc123",  # rev-parse main (tip)
                "abc123\ndef456\nxyz789",  # rev-list main (commits)
                "",  # for-each-ref returns empty (no parent found)
                "",  # continue walking...
            ]

            result = find_parent_branch()
            # Main is a root branch, has no parent
            assert result is None

    def test_find_parent_task_branch(self) -> None:
        """Test finding parent for task/issue-* branch."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            # Simulate a task branch with a parent
            mock_git.side_effect = [
                "task/issue-456",  # rev-parse --abbrev-ref HEAD
                "def456",  # rev-parse task/issue-456 (tip)
                "abc123\ndef456\nxyz789",  # rev-list (commits)
                "main\ndev/issue-123",  # for-each-ref (contains commit)
            ]

            result = find_parent_branch()
            # Should find parent among available branches
            assert result in ["main", "dev/issue-123"]

    def test_find_parent_performance_no_subprocess_explosion(self) -> None:
        """Test that find_parent_branch doesn't spawn O(K) subprocesses."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            # Simulate 250 local branches (worst case scenario)
            # But the optimized algorithm should only call git for-each-ref
            # a handful of times (once per commit until parent found)

            # branches would be 250 local branches in worst case
            # (not used in mock, but documents the scenario)
            current_branch = "task/issue-200"

            # First few commits before finding parent
            commits = [f"commit{i}" for i in range(10)]

            # Mock responses
            mock_git.side_effect = [
                current_branch,  # rev-parse --abbrev-ref HEAD
                "tip123",  # rev-parse current_branch (tip)
                "\n".join(commits),  # rev-list current_branch
                "main",  # for-each-ref for second commit (found parent!)
            ]

            result = find_parent_branch()

            # Should complete and find a parent
            assert result is not None

            # Verify number of git calls is small
            # Should be: rev-parse, rev-parse (tip), rev-list, for-each-ref
            # NOT 250+ calls (old O(K) behavior)
            assert mock_git.call_count <= 10, (
                f"Expected <= 10 git calls, got {mock_git.call_count}. "
                "This suggests subprocess explosion (O(K) instead of O(N))."
            )

    def test_find_parent_no_parent_found(self) -> None:
        """Test when no parent branch can be found."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            mock_git.side_effect = [
                "orphan-branch",  # rev-parse --abbrev-ref HEAD
                "abc123",  # rev-parse orphan-branch (tip)
                "abc123\ndef456",  # rev-list orphan-branch
                "",  # for-each-ref returns empty (no candidates)
                "",  # for-each-ref for next commit (still nothing)
            ]

            result = find_parent_branch()
            # Should return None when no parent found
            # (after checking a few commits)
            assert result is None

    def test_find_parent_with_explicit_branch_param(self) -> None:
        """Test that current_branch parameter is used when provided."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            # When branch is provided, should skip the rev-parse HEAD call
            mock_git.side_effect = [
                "feature/test",  # rev-parse feature/test (tip)
                "abc123\ndef456",  # rev-list feature/test
                "main",  # for-each-ref finds parent
            ]

            result = find_parent_branch(current_branch="feature/test")
            assert result in ["main", "feature/test"]

            # Should not call rev-parse HEAD
            calls = [str(call) for call in mock_git.call_args_list]
            assert not any("HEAD" in str(call) for call in calls)

    def test_find_parent_git_error(self) -> None:
        """Test handling of git command errors."""
        with patch("vibe3.utils.branch_utils._run_git") as mock_git:
            # Simulate git command failure
            mock_git.side_effect = Exception("git command failed")

            result = find_parent_branch()
            # Should return None on error (logged but not raised)
            assert result is None
