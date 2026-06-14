"""Tests for review_pipeline_helpers."""

from unittest.mock import MagicMock, patch

from vibe3.agents.review_pipeline_helpers import build_snapshot_diff
from vibe3.analysis import SnapshotError


@patch("vibe3.agents.review_pipeline_helpers.find_snapshot_by_branch")
def test_build_snapshot_diff_no_baseline(mock_find):
    """Test when no baseline snapshot is found."""
    mock_find.return_value = None
    result = build_snapshot_diff(base_branch="main")
    assert result is None
    mock_find.assert_called_once_with("main", None)


@patch("vibe3.agents.review_pipeline_helpers.compute_diff")
@patch("vibe3.agents.review_pipeline_helpers.build_snapshot")
@patch("vibe3.agents.review_pipeline_helpers.find_snapshot_by_branch")
def test_build_snapshot_diff_success(mock_find, mock_build, mock_compute):
    """Test successful build of snapshot diff."""
    mock_baseline = MagicMock()
    mock_current = MagicMock()
    mock_diff = MagicMock()
    mock_diff.summary.files_added = 1
    mock_diff.summary.files_removed = 2
    mock_diff.summary.files_modified = 3

    mock_find.return_value = mock_baseline
    mock_build.return_value = mock_current
    mock_compute.return_value = mock_diff

    result = build_snapshot_diff(base_branch="main", current_branch="feature")

    assert result == mock_diff
    mock_find.assert_called_once_with("main", "feature")
    mock_build.assert_called_once()
    mock_compute.assert_called_once_with(mock_baseline, mock_current)


@patch("vibe3.agents.review_pipeline_helpers.find_snapshot_by_branch")
def test_build_snapshot_diff_snapshot_error(mock_find):
    """Test handling of SnapshotError."""
    mock_find.side_effect = SnapshotError("Test error")
    result = build_snapshot_diff()
    assert result is None


@patch("vibe3.agents.review_pipeline_helpers.find_snapshot_by_branch")
def test_build_snapshot_diff_unexpected_error(mock_find):
    """Test handling of unexpected exceptions."""
    mock_find.side_effect = Exception("Unexpected error")
    result = build_snapshot_diff()
    assert result is None
