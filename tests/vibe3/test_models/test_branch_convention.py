"""Tests for BranchConvention model."""

import pytest

from vibe3.models.branch_convention import BranchConvention


def test_canonical_branch_vibe_center():
    """Test canonical branch generation for Vibe Center convention."""
    convention = BranchConvention.vibe_center()
    assert convention.canonical_branch(123) == "task/issue-123"


def test_dev_branch_vibe_center():
    """Test dev branch generation for Vibe Center convention."""
    convention = BranchConvention.vibe_center()
    assert convention.dev_branch(123) == "dev/issue-123"


def test_parse_issue_number_vibe_center():
    """Test issue number parsing for Vibe Center convention."""
    convention = BranchConvention.vibe_center()
    assert convention.parse_issue_number("task/issue-372") == 372
    assert convention.parse_issue_number("dev/issue-328") == 328
    assert convention.parse_issue_number("feature/my-feature") is None


def test_minimal_convention():
    """Test minimal convention for generic repos."""
    convention = BranchConvention.minimal()
    assert convention.canonical_branch(456) == "issue-456"
    assert convention.dev_branch(456) == "issue-456"
    assert convention.parse_issue_number("issue-456") == 456


def test_immutable_convention():
    """Test that convention is immutable (frozen dataclass)."""
    convention = BranchConvention(task_prefix="task/", dev_prefix="dev/")
    with pytest.raises(AttributeError):
        convention.task_prefix = "new-"
