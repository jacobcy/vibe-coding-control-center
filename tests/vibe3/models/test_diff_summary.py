"""Tests for DiffSummary model."""

from vibe3.models import DiffSummary


def test_diff_summary_addition():
    """Test that DiffSummary instances can be added together."""
    summary1 = DiffSummary(
        files_added=2,
        files_removed=1,
        files_modified=3,
        total_loc_delta=150,
    )

    summary2 = DiffSummary(
        files_added=1,
        files_removed=2,
        files_modified=1,
        total_loc_delta=50,
    )

    result = summary1 + summary2

    assert result.files_added == 3
    assert result.files_removed == 3
    assert result.files_modified == 4
    assert result.total_loc_delta == 200


def test_diff_summary_default_values():
    """Test that DiffSummary initializes with zero defaults."""
    summary = DiffSummary()

    assert summary.files_added == 0
    assert summary.files_removed == 0
    assert summary.files_modified == 0
    assert summary.total_loc_delta == 0


def test_diff_summary_add_with_empty():
    """Test adding empty summary to a non-empty one."""
    summary1 = DiffSummary(files_added=5, total_loc_delta=100)
    summary2 = DiffSummary()

    result = summary1 + summary2

    assert result.files_added == 5
    assert result.total_loc_delta == 100
