"""Tests for git-based diff summary."""

from unittest.mock import Mock, patch

from vibe3.analysis.git_diff_summary import get_git_diff_summary
from vibe3.models import DiffSummary


def test_get_git_diff_summary_basic():
    """Test basic git diff summary generation."""
    mock_git = Mock()
    mock_git.get_merge_base.return_value = "abc123"
    # Provide separate outputs for committed and uncommitted sources
    # The function calls get_numstat twice (committed + uncommitted)
    mock_git.get_numstat.side_effect = [
        "10\t5\tfile1.py\n20\t0\tfile2.py\n0\t3\tfile3.py",  # committed
        "",  # uncommitted (empty)
    ]
    mock_git.get_name_status.side_effect = [
        "A\tfile1.py\nM\tfile2.py\nD\tfile3.py",  # committed
        "",  # uncommitted (empty)
    ]

    with patch("vibe3.analysis.git_diff_summary.GitClient", return_value=mock_git):
        result = get_git_diff_summary("feature-branch", "main")

    assert isinstance(result, DiffSummary)
    assert result.files_added == 1
    assert result.files_removed == 1
    assert result.files_modified == 1
    assert result.total_loc_delta == 22  # (10-5) + (20-0) + (0-3) = 5 + 20 - 3 = 22


def test_get_git_diff_summary_merge_base_failure():
    """Test that get_git_diff_summary handles merge-base resolution failure."""
    mock_git = Mock()
    mock_git.get_merge_base.side_effect = Exception("Merge base not found")
    # Provide separate outputs for committed and uncommitted sources
    mock_git.get_numstat.side_effect = [
        "5\t2\tfile.py",  # committed
        "",  # uncommitted (empty)
    ]
    mock_git.get_name_status.side_effect = [
        "M\tfile.py",  # committed
        "",  # uncommitted (empty)
    ]

    with patch("vibe3.analysis.git_diff_summary.GitClient", return_value=mock_git):
        result = get_git_diff_summary("feature-branch", "main")

    # Should fall back to base_branch when merge-base fails
    assert isinstance(result, DiffSummary)
    assert result.files_modified == 1
    assert result.total_loc_delta == 3


def test_get_git_diff_summary_empty():
    """Test git diff summary with no changes."""
    mock_git = Mock()
    mock_git.get_merge_base.return_value = "abc123"
    mock_git.get_numstat.side_effect = ["", ""]  # Both committed and uncommitted empty
    mock_git.get_name_status.side_effect = ["", ""]

    with patch("vibe3.analysis.git_diff_summary.GitClient", return_value=mock_git):
        result = get_git_diff_summary("feature-branch", "main")

    assert isinstance(result, DiffSummary)
    assert result.files_added == 0
    assert result.files_removed == 0
    assert result.files_modified == 0
    assert result.total_loc_delta == 0


def test_get_git_diff_summary_with_renames():
    """Test git diff summary handles renames correctly."""
    mock_git = Mock()
    mock_git.get_merge_base.return_value = "abc123"
    mock_git.get_numstat.side_effect = [
        "10\t0\tnew_file.py\n0\t10\told_file.py",  # committed
        "",  # uncommitted (empty)
    ]
    mock_git.get_name_status.side_effect = [
        "R100\told_file.py\tnew_file.py",  # committed
        "",  # uncommitted (empty)
    ]

    with patch("vibe3.analysis.git_diff_summary.GitClient", return_value=mock_git):
        result = get_git_diff_summary("feature-branch", "main")

    # Rename counts as 1 added + 1 removed
    assert result.files_added == 1
    assert result.files_removed == 1
